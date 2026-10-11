"""Host-run unittest for apps.web.run_recovery (leftover: restart auto-recovery).

The decision helpers must be host-importable (stdlib-only) because
apps.web.run_manager pulls pydantic via control_adapter and cannot be imported
on the bare host.
"""

from __future__ import annotations

import unittest

from apps.web.run_recovery import (
    auto_resume_enabled,
    auto_resume_stagger_s,
    newest_generation_interrupted,
)


def finished_row(reason: str, generation: int, seq: int = 1) -> dict:
    return {
        "event_type": "run.finished",
        "seq": seq,
        "payload": {
            "reason": reason,
            "execution_generation": generation,
            "solved": False,
        },
    }


class NewestGenerationInterruptedTests(unittest.TestCase):
    def test_interrupted_terminal_for_generation_is_true(self):
        rows = [
            {"event_type": "run.started", "payload": {}},
            finished_row("interrupted", 3, seq=7),
        ]
        self.assertTrue(newest_generation_interrupted(rows, 3))

    def test_no_rows_or_nonpositive_generation_is_false(self):
        self.assertFalse(newest_generation_interrupted([], 3))
        self.assertFalse(newest_generation_interrupted(
            [finished_row("interrupted", 3)], 0))
        self.assertFalse(newest_generation_interrupted(
            [finished_row("interrupted", 3)], -1))

    def test_terminal_of_other_generation_does_not_count(self):
        rows = [finished_row("interrupted", 2, seq=4)]
        self.assertFalse(newest_generation_interrupted(rows, 3))

    def test_later_generation_terminal_supersedes_older_interrupted(self):
        # gen 2 closed interrupted, then resolve() opened gen 3 which solved:
        # the run is NOT pending recovery.
        rows = [
            finished_row("interrupted", 2, seq=4),
            finished_row("solved", 3, seq=9),
        ]
        self.assertFalse(newest_generation_interrupted(rows, 3))
        # and the older generation itself still reads as interrupted
        self.assertTrue(newest_generation_interrupted(rows, 2))

    def test_non_interrupted_reason_is_false(self):
        for reason in ("solved", "failed", "budget_exhausted", "cancelled", ""):
            self.assertFalse(newest_generation_interrupted(
                [finished_row(reason, 1)], 1), reason)

    def test_missing_generation_tag_is_ignored(self):
        rows = [{
            "event_type": "run.finished",
            "payload": {"reason": "interrupted"},  # no execution_generation
        }]
        self.assertFalse(newest_generation_interrupted(rows, 1))


class AutoResumeGateTests(unittest.TestCase):
    def test_default_is_off(self):
        self.assertFalse(auto_resume_enabled(env={}))

    def test_truthy_values_enable(self):
        for raw in ("1", "true", "YES", "on"):
            self.assertTrue(auto_resume_enabled(
                env={"MUTEKI_AUTO_RESUME": raw}), raw)

    def test_falsy_values_disable(self):
        for raw in ("0", "false", "no", "off", "", "  "):
            self.assertFalse(auto_resume_enabled(
                env={"MUTEKI_AUTO_RESUME": raw}), raw)

    def test_stagger_defaults_to_five_seconds(self):
        self.assertEqual(auto_resume_stagger_s(env={}), 5.0)

    def test_stagger_override_and_floor(self):
        self.assertEqual(
            auto_resume_stagger_s(env={"MUTEKI_AUTO_RESUME_STAGGER_S": "12"}),
            12.0)
        self.assertEqual(
            auto_resume_stagger_s(env={"MUTEKI_AUTO_RESUME_STAGGER_S": "-3"}),
            0.0)
        self.assertEqual(
            auto_resume_stagger_s(env={"MUTEKI_AUTO_RESUME_STAGGER_S": "x"}),
            5.0)


if __name__ == "__main__":
    unittest.main()
