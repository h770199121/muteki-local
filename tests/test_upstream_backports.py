"""Offline regressions for selected upstream runtime backports."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from muteki.models.solve_graph import Challenge
from muteki.solver.cli_driver import CliResult, DRIVERS, run_cli, run_cli_streaming
from muteki.solver.cli_solver import CliSolver
from muteki.solver.container_exec import ContainerHandle, _DockerExecBackend


class UpstreamBackportTests(unittest.TestCase):
    def solver(self, **kwargs):
        challenge = Challenge(id="upstream-test", name="offline fixture", category="misc",
                              description="context " * 160 + "REQUIRED_TAIL_SENTINEL",
                              flag_format="flag{...}")
        return CliSolver(None, challenge, engine="dsh", web_access=False, kb=False, **kwargs)

    def test_required_description_survives_all_prompt_builders(self):
        solver = self.solver()
        for builder in (solver._build_prompt, solver._build_explore_prompt, solver._build_review_prompt):
            with self.subTest(builder=builder.__name__):
                self.assertIn("REQUIRED_TAIL_SENTINEL", builder())

    def test_course_correction_is_not_cut_at_600_characters(self):
        solver = self.solver(intent_goal="context " * 160 + "CORRECTION_TAIL_SENTINEL")
        self.assertIn("CORRECTION_TAIL_SENTINEL", solver._build_prompt())

    def test_worker_disables_bytecode_for_read_only_skill_sources(self):
        self.assertEqual(self.solver()._worker_env().get("PYTHONDONTWRITEBYTECODE"), "1")

    def test_skill_staging_failure_has_an_environment_code(self):
        from muteki.solver.cli_launch_check import LaunchContractError
        with tempfile.TemporaryDirectory() as work:
            with patch("muteki.solver.worker_skills.stage_blackboard_skill", side_effect=PermissionError("fixture directory")):
                with self.assertRaises(LaunchContractError) as result:
                    self.solver(workdir=work)._worker_env()
        self.assertEqual(result.exception.code, "worker_environment_unavailable")
        self.assertIn("worker_environment_unavailable", str(result.exception))

    def test_nul_argv_is_rejected_before_any_process(self):
        from muteki.solver.cli_launch_check import LaunchContractError
        driver = SimpleNamespace(env_extra=lambda: {}, parse=lambda out, err: CliResult(text=out))
        with patch("muteki.solver.cli_driver.subprocess.run") as spawn:
            with self.assertRaises(LaunchContractError) as result:
                run_cli(driver, ["python3", "bad\x00argument"], cwd="/tmp", timeout=2)
        spawn.assert_not_called()
        self.assertEqual(result.exception.code, "process_input_illegal")

    def test_oversized_env_is_rejected_before_streaming_process(self):
        from muteki.solver.cli_launch_check import LaunchContractError
        driver = SimpleNamespace(env_extra=lambda: {}, parse=lambda out, err: CliResult(text=out))
        with patch("subprocess.Popen") as spawn:
            with self.assertRaises(LaunchContractError) as result:
                run_cli_streaming(driver, ["python3"], cwd="/tmp", timeout=2,
                                  on_step=lambda _: None, env={"TEST_DATA": "x" * (128 * 1024)})
        spawn.assert_not_called()
        self.assertEqual(result.exception.code, "process_argv_too_large")

    def test_invalid_container_request_is_rejected_before_dispatch(self):
        from muteki.solver.cli_launch_check import LaunchContractError
        with patch("muteki.solver.container_exec.run_cli_container") as dispatch:
            with self.assertRaises(LaunchContractError):
                run_cli(DRIVERS["dsh"], ["python3", "bad\x00argument"], cwd="/tmp",
                        timeout=2, container=object())
        dispatch.assert_not_called()

    def test_docker_shell_quoting_is_checked_after_expansion(self):
        from muteki.solver.cli_launch_check import LaunchContractError
        handle = ContainerHandle(run_id="fixture", host_workspace="/tmp", container="fixture")
        with self.assertRaises(LaunchContractError) as result:
            _DockerExecBackend._exec_argv(handle, ["python3", "bridge.py", "--", "'" * 40000],
                container_cwd="/tmp", env={}, driver_name="dsh", tag="fixture", timeout=2)
        self.assertEqual(result.exception.code, "process_argv_too_large")

    def test_streamed_stdin_is_not_counted_as_argv(self):
        driver = SimpleNamespace(env_extra=lambda: {}, parse=lambda out, err: CliResult(text=out),
                                 parse_stream_steps=lambda _: [])
        text = "x" * (150 * 1024)
        with tempfile.TemporaryDirectory() as work:
            result = run_cli_streaming(driver, [sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"],
                cwd=work, timeout=10, on_step=lambda _: None, stdin_text=text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.text.strip(), str(len(text)))

    def test_local_engines_are_retained(self):
        self.assertIn("dsh", DRIVERS)
        self.assertIn("zcode", DRIVERS)


if __name__ == "__main__":
    unittest.main()
