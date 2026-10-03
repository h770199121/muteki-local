"""D04 — pre-start dispatch failures must stop being re-dispatched.

A worker that never starts looks identical to one that is merely slow. Without a
distinction the Coordinator re-dispatches the same broken configuration until the
wall clock expires, and the run is reported "unsolved" — which reads like a reasoning
failure but is really an environment failure.

Upstream solves this in ``coordinator_worker_reap.py``; it is NOT copied because it
depends on ``coordinator_state`` / ``runtime_terminal_failure`` /
``_runtime_failure_code`` / ``_runtime_failure_phase``, none of which exist in this
0.3.2-derived tree. These tests pin the SEMANTICS re-implemented against what this
tree actually has.

What must hold
--------------
* only pre-start rejections count toward the streak;
* a real process-start receipt clears it (task creation does not);
* the limit stops the run and names the real cause;
* the threshold is configurable and can be disabled explicitly;
* the pre-existing fruitless-interrupt path is untouched (no stacked counters).

Run:  python -X utf8 -B -m unittest tests.test_dispatch_failure_governor -v
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from muteki.swarm.dispatch_failure_governor import (  # noqa: E402
    DEFAULT_MAX_CONSECUTIVE_FAILURES,
    ENV_MAX_FAILURES,
    PRESTART_REJECTIONS,
    FailureGovernor,
    is_prestart_rejection,
    resolve_failure_limit,
    summarize_active_solvers,
    worker_is_prestart,
)

MODULE = ROOT / "muteki" / "swarm" / "dispatch_failure_governor.py"


class PrestartClassificationTests(unittest.TestCase):
    def test_dispatch_rejections_are_prestart(self):
        for reason in ("worker_spawn_rejected", "max_workers",
                       "unavailable_profile", "unknown_engine",
                       "process_input_illegal", "process_argv_too_large",
                       "worker_environment_unavailable"):
            with self.subTest(reason=reason):
                self.assertTrue(is_prestart_rejection(reason))

    def test_qualified_reason_is_recognised(self):
        self.assertTrue(is_prestart_rejection("worker_spawn_rejected:max_workers"))

    def test_runtime_failures_are_not_prestart(self):
        for reason in ("model_timeout", "target_unreachable", "tool_crash",
                       "flag_rejected", ""):
            with self.subTest(reason=reason):
                self.assertFalse(is_prestart_rejection(reason))

    def test_rejection_set_is_non_empty(self):
        self.assertGreater(len(PRESTART_REJECTIONS), 0)


class StreakCountingTests(unittest.TestCase):
    def test_streak_reaches_limit_exactly_at_threshold(self):
        gov = FailureGovernor(limit=3)
        self.assertFalse(gov.record_failure(worker="w", engine="dsh",
                                           detail="a", reason="unknown_engine"))
        self.assertFalse(gov.record_failure(worker="w", engine="dsh",
                                           detail="b", reason="unknown_engine"))
        self.assertTrue(gov.record_failure(worker="w", engine="dsh",
                                          detail="c", reason="unknown_engine"))
        self.assertTrue(gov.limit_reached)

    def test_runtime_failure_is_not_counted(self):
        gov = FailureGovernor(limit=2)
        gov.record_failure(worker="w", engine="dsh", detail="模型超时",
                           reason="model_timeout")
        self.assertEqual(gov.consecutive, 0)
        self.assertFalse(gov.limit_reached)

    def test_mixed_failures_only_count_the_prestart_ones(self):
        gov = FailureGovernor(limit=3)
        gov.record_failure(worker="w", engine="dsh", detail="x", reason="unknown_engine")
        gov.record_failure(worker="w", engine="dsh", detail="运行期", reason="model_timeout")
        gov.record_failure(worker="w", engine="dsh", detail="y", reason="max_workers")
        self.assertEqual(gov.consecutive, 2)

    def test_disabled_governor_never_counts(self):
        gov = FailureGovernor(limit=0)
        for _ in range(10):
            self.assertFalse(gov.record_failure(worker="w", engine="dsh",
                                                detail="d", reason="unknown_engine"))
        self.assertEqual(gov.consecutive, 0)
        self.assertFalse(gov.limit_reached)
        self.assertFalse(gov.enabled)


class StartReceiptTests(unittest.TestCase):
    def test_start_receipt_clears_the_streak(self):
        gov = FailureGovernor(limit=5)
        gov.record_failure(worker="w", engine="dsh", detail="d", reason="unknown_engine")
        gov.record_failure(worker="w", engine="dsh", detail="d", reason="unknown_engine")
        self.assertEqual(gov.consecutive, 2)
        previous = gov.record_start_observed("w2")
        self.assertEqual(previous, 2)
        self.assertEqual(gov.consecutive, 0)

    def test_start_receipt_with_nothing_pending_returns_zero(self):
        # Callers use this to skip emitting a recovery event on the common path.
        self.assertEqual(FailureGovernor(limit=3).record_start_observed("w"), 0)

    def test_start_after_limit_does_not_resurrect_the_stop(self):
        gov = FailureGovernor(limit=1)
        gov.record_failure(worker="w", engine="dsh", detail="d", reason="unknown_engine")
        self.assertTrue(gov.limit_reached)
        gov.record_start_observed("w")
        self.assertTrue(gov.limit_reached, "已达上限后不应因新启动而复活")

    def test_recovery_is_recorded_in_history(self):
        gov = FailureGovernor(limit=5)
        gov.record_failure(worker="w", engine="dsh", detail="d", reason="unknown_engine")
        gov.record_start_observed("w2")
        self.assertEqual(gov.history[-1]["event"], "recovered")
        self.assertEqual(gov.history[-1]["previous_consecutive_failures"], 1)


class StopReasonTests(unittest.TestCase):
    def test_stop_reason_names_the_cause_not_just_a_count(self):
        gov = FailureGovernor(limit=2)
        gov.record_failure(worker="w", engine="zcode", detail="requested profile is unavailable",
                           reason="unavailable_profile")
        gov.record_failure(worker="w", engine="zcode", detail="requested profile is unavailable",
                           reason="unavailable_profile")
        reason = gov.stop_reason()
        self.assertIn("zcode", reason)
        self.assertIn("unavailable", reason)

    def test_no_stop_reason_before_the_limit(self):
        gov = FailureGovernor(limit=3)
        gov.record_failure(worker="w", engine="dsh", detail="d", reason="unknown_engine")
        self.assertEqual(gov.stop_reason(), "")

    def test_failure_code_is_stable(self):
        self.assertEqual(FailureGovernor(limit=1).failure_code(),
                         "consecutive_worker_dispatch_failures")

    def test_remaining_counts_down(self):
        gov = FailureGovernor(limit=3)
        self.assertEqual(gov.remaining(), 3)
        gov.record_failure(worker="w", engine="dsh", detail="d", reason="unknown_engine")
        self.assertEqual(gov.remaining(), 2)

    def test_remaining_is_none_once_reached(self):
        gov = FailureGovernor(limit=1)
        gov.record_failure(worker="w", engine="dsh", detail="d", reason="unknown_engine")
        self.assertIsNone(gov.remaining())


class LimitResolutionTests(unittest.TestCase):
    def test_default_is_upstreams_value_documented_as_such(self):
        self.assertEqual(resolve_failure_limit({}), DEFAULT_MAX_CONSECUTIVE_FAILURES)
        source = MODULE.read_text(encoding="utf-8")
        self.assertIn("DEFAULT_MAX_CONSECUTIVE_FAILURES = 5", source)

    def test_env_override(self):
        self.assertEqual(resolve_failure_limit({ENV_MAX_FAILURES: "9"}), 9)

    def test_malformed_limit_falls_back_and_does_not_disable(self):
        # A typo must not silently switch the governor off.
        self.assertEqual(resolve_failure_limit({ENV_MAX_FAILURES: "很多"}),
                         DEFAULT_MAX_CONSECUTIVE_FAILURES)

    def test_zero_explicitly_disables(self):
        self.assertEqual(resolve_failure_limit({ENV_MAX_FAILURES: "0"}), 0)


class SolverStateTests(unittest.TestCase):
    class _Solver:
        def __init__(self, started=False, committed=False, unknown=False, done=False):
            self._runtime_process_started = started
            self._control_context_delivery_committed = committed
            self._control_context_delivery_unknown = unknown
            self.solver_id = "s1"
            self._done = done

        def done(self):
            return self._done

    def test_not_started_is_prestart(self):
        self.assertTrue(worker_is_prestart(self._Solver(started=False)))

    def test_started_solver_is_not_prestart(self):
        self.assertFalse(worker_is_prestart(self._Solver(started=True)))

    def test_delivered_context_is_not_prestart(self):
        # The operator's instruction already reached the runtime, so this is not a
        # "never started" case even if no process receipt exists.
        self.assertFalse(worker_is_prestart(self._Solver(started=False, committed=True)))
        self.assertFalse(worker_is_prestart(self._Solver(started=False, unknown=True)))

    def test_summary_counts_states_and_skips_done(self):
        solvers = [self._Solver(started=True), self._Solver(started=False),
                   self._Solver(started=False), self._Solver(done=True)]
        summary = summarize_active_solvers(solvers)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["started"], 1)
        self.assertEqual(summary["prestart"], 2)


class WiringTests(unittest.TestCase):
    """The governor must actually be wired, not merely defined."""

    def test_dispatch_reports_prestart_rejections_to_it(self):
        source = (ROOT / "muteki" / "swarm" / "coordinator_dispatch.py").read_text(
            encoding="utf-8")
        self.assertIn("_note_worker_dispatch_failure", source)
        self.assertIn('kind == "worker_spawn_rejected"', source)

    def test_state_is_initialised_on_the_coordinator(self):
        source = (ROOT / "muteki" / "swarm" / "swarm.py").read_text(encoding="utf-8")
        self.assertIn("_dispatch_failure_governor", source)
        self.assertIn("_dispatch_failure_limit_reached", source)

    def test_uses_the_real_solver_registry(self):
        source = (ROOT / "muteki" / "swarm" / "coordinator_dispatch.py").read_text(
            encoding="utf-8")
        # A cache that nothing populates would mean the streak is never cleared.
        self.assertIn("_live_solvers", source)
        self.assertNotIn("_active_solvers_cache", source)

    def test_does_not_duplicate_the_fruitless_counter(self):
        # D04 must not stack a second, conflicting stall counter.
        source = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("fruitless", source.replace(
            "fruitless-interrupt", "").replace("fruitless interrupt", ""))

    def test_module_is_dependency_free(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported <= {"__future__", "os", "dataclasses", "typing"},
                        f"引入了非标准库依赖: {imported}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
