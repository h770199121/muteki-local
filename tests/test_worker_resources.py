"""D07 — worker container resource limits must be configurable and observable.

``container_exec`` already appended ``--memory`` / ``--cpus`` / ``--pids-limit`` when
given values, but the single production call site passed none, so worker containers
ran uncapped on a host sharing CPU/RAM with the local model.

This module has no third-party imports on purpose: the project venv cannot import
pydantic, so ``muteki.solver.worker_resources`` is exercised directly.

What must hold
--------------
* unset stays unset — we do NOT invent upstream's 2GB/2CPU default, because
  Ghidra/Sage often need more and a wrong cap looks like a broken challenge;
* a malformed value is reported, never silently dropped;
* ``MUTEKI_WORKER_RESOURCES_REQUIRED=1`` turns a malformed value into a hard error;
* the resolved limits reach ``ensure_container`` and the docker argv;
* the Coordinator records the effective values, including "unlimited".

Run:  python -X utf8 -B -m unittest tests.test_worker_resources -v
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from muteki.solver.worker_resources import (  # noqa: E402
    ENV_CPUS,
    ENV_MEMORY,
    ENV_PIDS,
    ENV_REQUIRED,
    ResourceConfigError,
    ResourceLimits,
    describe_limits,
    resolve_limits,
)

MODULE = ROOT / "muteki" / "solver" / "worker_resources.py"


class UnsetIsValidTests(unittest.TestCase):
    def test_empty_env_is_unlimited_not_an_error(self):
        limits = resolve_limits({})
        self.assertTrue(limits.unlimited)
        self.assertFalse(limits.any_set)
        self.assertEqual(limits.as_docker_args(), [])

    def test_unlimited_is_reported_explicitly(self):
        text = describe_limits(resolve_limits({}))
        self.assertIn("unlimited", text)
        self.assertIn("no explicit resource limit", text)

    def test_to_dict_marks_unconfigured(self):
        payload = ResourceLimits().to_dict()
        self.assertEqual(payload["memory"], "unlimited")
        self.assertEqual(payload["cpus"], "unlimited")
        self.assertEqual(payload["pids_limit"], "unlimited")
        self.assertFalse(payload["configured"])

    def test_partial_configuration_keeps_the_rest_unset(self):
        limits = resolve_limits({ENV_MEMORY: "8g"})
        self.assertEqual(limits.memory, "8g")
        self.assertIsNone(limits.cpus)
        self.assertIsNone(limits.pids_limit)
        self.assertEqual(limits.as_docker_args(), ["--memory", "8g"])


class NoInventedDefaultTests(unittest.TestCase):
    """D07: upstream's full preset must not leak in as our default."""

    def test_no_default_limits_are_applied(self):
        limits = resolve_limits({})
        self.assertIsNone(limits.memory)
        self.assertIsNone(limits.cpus)
        self.assertIsNone(limits.pids_limit)

    def test_module_declares_no_preset(self):
        source = MODULE.read_text(encoding="utf-8")
        # A 2g/2 CPU default would re-create the exact problem D07 fixes.
        code = "\n".join(l for l in source.splitlines()
                         if not l.lstrip().startswith("#"))
        self.assertNotIn('"2g"', code)
        self.assertNotIn('"2.0"', code.replace("cpus=2.0", "").replace("8g, 2.0", ""))


class ValidationTests(unittest.TestCase):
    def test_valid_values_are_accepted(self):
        limits = resolve_limits({
            ENV_MEMORY: "8g", ENV_CPUS: "2.0", ENV_PIDS: "512",
        })
        self.assertEqual(limits.memory, "8g")
        self.assertEqual(limits.cpus, "2.0")
        self.assertEqual(limits.pids_limit, 512)
        self.assertEqual(limits.warnings, ())

    def test_memory_forms(self):
        for value in ("8g", "512m", "1.5g", "2048", "4G"):
            with self.subTest(value=value):
                self.assertEqual(resolve_limits({ENV_MEMORY: value}).memory, value)

    def test_malformed_value_is_reported_not_dropped_silently(self):
        limits = resolve_limits({ENV_MEMORY: "很多"})
        self.assertIsNone(limits.memory)
        self.assertTrue(limits.warnings, "非法值必须被记录")
        self.assertIn("MUTEKI_WORKER_MEMORY", limits.warnings[0])

    def test_malformed_value_is_mentioned_in_the_summary(self):
        text = describe_limits(resolve_limits({ENV_PIDS: "很多"}))
        self.assertIn("ignored", text)

    def test_required_mode_turns_malformed_into_hard_error(self):
        with self.assertRaises(ResourceConfigError):
            resolve_limits({ENV_MEMORY: "很多", ENV_REQUIRED: "1"})

    def test_required_mode_still_allows_valid_values(self):
        limits = resolve_limits({ENV_MEMORY: "8g", ENV_REQUIRED: "true"})
        self.assertEqual(limits.memory, "8g")

    def test_zero_and_negative_are_rejected(self):
        for var, value in ((ENV_CPUS, "0"), (ENV_PIDS, "-1"), (ENV_PIDS, "0")):
            with self.subTest(var=var, value=value):
                self.assertTrue(resolve_limits({var: value}).warnings)

    def test_one_bad_value_does_not_discard_the_good_ones(self):
        limits = resolve_limits({ENV_MEMORY: "8g", ENV_CPUS: "很多", ENV_PIDS: "256"})
        self.assertEqual(limits.memory, "8g")
        self.assertEqual(limits.pids_limit, 256)
        self.assertIsNone(limits.cpus)


class DockerArgTests(unittest.TestCase):
    def test_all_three_flags_render_in_order(self):
        limits = resolve_limits({
            ENV_MEMORY: "8g", ENV_CPUS: "2.0", ENV_PIDS: "512",
        })
        self.assertEqual(limits.as_docker_args(),
                         ["--memory", "8g", "--cpus", "2.0", "--pids-limit", "512"])

    def test_kwargs_shape_matches_ensure_container(self):
        limits = resolve_limits({ENV_MEMORY: "8g", ENV_PIDS: "512"})
        kwargs = limits.as_kwargs()
        self.assertEqual(set(kwargs), {"memory", "cpus", "pids_limit"})
        self.assertEqual(kwargs["memory"], "8g")
        self.assertIsNone(kwargs["cpus"])

    def test_pids_zero_is_not_rendered(self):
        # container_exec guards on int(pids_limit) > 0; make sure we never emit a
        # meaningless --pids-limit 0.
        self.assertEqual(ResourceLimits(pids_limit=0).as_docker_args(), [])


class WiringTests(unittest.TestCase):
    """The limits must actually reach ensure_container on the production path."""

    def test_coordinator_passes_resolved_limits(self):
        source = (ROOT / "muteki" / "swarm" / "coordinator_race.py").read_text(
            encoding="utf-8")
        self.assertIn("resolve_limits()", source)
        self.assertIn("**limits.as_kwargs()", source,
                      "Coordinator 必须把解析出的限额传给 ensure_container")

    def test_coordinator_records_the_effective_limits(self):
        source = (ROOT / "muteki" / "swarm" / "coordinator_race.py").read_text(
            encoding="utf-8")
        self.assertIn("_record_worker_resource_limits", source)

    def test_state_field_is_initialised(self):
        source = (ROOT / "muteki" / "swarm" / "swarm.py").read_text(encoding="utf-8")
        self.assertIn("_worker_resource_limits", source,
                      "必须初始化 _worker_resource_limits 状态字段")

    def test_module_is_dependency_free(self):
        """The venv has no pydantic; this module must import with stdlib only."""
        source = MODULE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported <= {"__future__", "os", "re", "dataclasses",
                                      "typing"},
                        f"引入了非标准库依赖: {imported}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
