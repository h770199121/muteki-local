"""A01 — usage reduction must not double-count cumulative snapshots.

``cost.update`` events are cumulative snapshots published at two scopes
(``solver`` and ``challenge``).  The evaluation harness summed them all, so a
single solver's successive snapshots were added together AND the challenge rollup
was added on top of the solvers it already contains.  For run-20670 that produced
6,312,289 / 185,575 instead of the solvers' actual 1,563,948 / 52,737.

These tests pin the reduction contract against both synthetic events and the real
archived run.

Run:  python -X utf8 -B -m unittest tests.test_usage_reduce -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "labs" / "nyu-ctf"))

from usage_reduce import (  # noqa: E402
    USAGE_STATS_VERSION,
    reduce_event_file,
    reduce_usage,
)


def cost_event(seq, scope, identity, in_tok, out_tok, usd=0.0, gen=1, challenge=None):
    payload = {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "usd": usd,
        "scope": scope,
        "execution_generation": gen,
        "control_generation": 0,
    }
    if scope == "solver":
        payload["solver_id"] = identity
    elif scope == "challenge":
        payload["challenge_id"] = identity
        payload["challenge_id"] = challenge or identity
    return {
        "event_type": "cost.update",
        "seq": seq,
        "run_id": "run-test",
        "solver_id": identity if scope == "solver" else None,
        "payload": payload,
    }


class DoubleCountingTests(unittest.TestCase):
    def test_repeated_snapshot_does_not_increase_usage(self):
        events = [
            cost_event(1, "solver", "a", 1000, 100),
            cost_event(2, "solver", "a", 1000, 100),  # duplicate publication
            cost_event(3, "solver", "a", 1000, 100),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.input_tokens, 1000)
        self.assertEqual(r.output_tokens, 100)

    def test_successive_snapshots_take_last_not_sum(self):
        events = [
            cost_event(1, "solver", "a", 100, 10),
            cost_event(2, "solver", "a", 500, 50),
            cost_event(3, "solver", "a", 900, 90),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.input_tokens, 900)
        self.assertEqual(r.output_tokens, 90)

    def test_solver_and_challenge_rollup_are_not_added_together(self):
        # The rollup already contains the solver's usage.
        events = [
            cost_event(1, "solver", "a", 1000, 100),
            cost_event(2, "challenge", "run-test", 1000, 100),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.input_tokens, 1000, "rollup 被重复计入")
        self.assertEqual(r.output_tokens, 100)

    def test_multiple_solvers_each_counted_once(self):
        events = [
            cost_event(1, "solver", "a", 300, 30),
            cost_event(2, "solver", "a", 300, 30),
            cost_event(3, "solver", "b", 200, 20),
            cost_event(4, "solver", "b", 200, 20),
            cost_event(5, "solver", "b", 200, 20),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.input_tokens, 500)
        self.assertEqual(r.output_tokens, 50)


class OrderingAndReplayTests(unittest.TestCase):
    def test_out_of_order_events_give_same_result(self):
        ordered = [
            cost_event(1, "solver", "a", 100, 10),
            cost_event(2, "solver", "a", 900, 90),
            cost_event(3, "solver", "b", 50, 5),
        ]
        shuffled = [ordered[2], ordered[0], ordered[1]]
        self.assertEqual(reduce_usage(ordered).to_dict(),
                         reduce_usage(shuffled).to_dict())

    def test_newer_execution_generation_wins_after_resume(self):
        # A resumed run restarts accumulation; the later generation is authoritative.
        events = [
            cost_event(9, "solver", "a", 5000, 500, gen=2),
            cost_event(1, "solver", "a", 9999, 999, gen=1),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.input_tokens, 5000)
        self.assertEqual(r.solver_totals["a"]["execution_generation"], 2)

    def test_duplicate_identical_events_are_idempotent(self):
        once = [cost_event(1, "solver", "a", 100, 10)]
        thrice = once * 3
        self.assertEqual(reduce_usage(once).to_dict(),
                         reduce_usage(thrice).to_dict())


class CoverageHonestyTests(unittest.TestCase):
    def test_rollup_only_events_report_rollup_basis(self):
        events = [cost_event(1, "challenge", "run-x", 400, 40)]
        r = reduce_usage(events)
        self.assertEqual(r.basis, "challenge_rollup")
        self.assertEqual(r.input_tokens, 400)

    def test_rollup_smaller_than_solver_total_flags_incomplete(self):
        # A solver that started after the rollup cannot be inside it; summing the two
        # would double-count, so the reduction must disclose the gap.
        events = [
            cost_event(1, "solver", "a", 1000, 100),
            cost_event(2, "challenge", "run-x", 900, 90),
            cost_event(3, "solver", "b", 5000, 500),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.basis, "solver_ledgers")
        self.assertEqual(r.input_tokens, 6000)
        self.assertFalse(r.telemetry_complete)
        self.assertTrue(r.incomplete_reasons)

    def test_no_events_is_explicitly_incomplete(self):
        r = reduce_usage([])
        self.assertEqual(r.basis, "none")
        self.assertFalse(r.telemetry_complete)
        self.assertIn("no cost.update events found", r.incomplete_reasons)

    def test_scope_falls_back_to_shape_when_absent(self):
        # Legacy events without an explicit scope but carrying a solver_id.
        event = {
            "event_type": "cost.update", "seq": 1, "run_id": "r",
            "solver_id": "a",
            "payload": {"input_tokens": 10, "output_tokens": 1, "solver_id": "a"},
        }
        r = reduce_usage([event, event])
        self.assertEqual(r.basis, "solver_ledgers")
        self.assertEqual(r.input_tokens, 10)

    def test_stats_version_is_emitted(self):
        r = reduce_usage([cost_event(1, "solver", "a", 1, 1)])
        self.assertEqual(r.to_dict()["usage_stats_version"], USAGE_STATS_VERSION)
        self.assertEqual(USAGE_STATS_VERSION, 2)


class ArchivedRunTests(unittest.TestCase):
    """The real run-20670 log must not reproduce the double-counted figure."""

    LOG = ROOT / "data" / "sessions" / "run-20670.jsonl"

    def setUp(self):
        if not self.LOG.is_file():
            self.skipTest("run-20670.jsonl 不在本地，跳过归档重放")

    def test_archived_run_does_not_report_the_double_counted_total(self):
        r = reduce_event_file(self.LOG)
        # The old naive sum produced exactly these numbers.
        self.assertNotEqual((r.input_tokens, r.output_tokens), (6312289, 185575))

    def test_archived_run_matches_solver_ledgers(self):
        r = reduce_event_file(self.LOG)
        self.assertEqual(r.basis, "solver_ledgers")
        self.assertEqual(r.input_tokens, 1563948)
        self.assertEqual(r.output_tokens, 52737)

    def test_archived_run_discloses_incompleteness(self):
        r = reduce_event_file(self.LOG)
        self.assertFalse(r.telemetry_complete)
        self.assertTrue(r.incomplete_reasons)

    def test_archived_run_keeps_snapshots_separate(self):
        r = reduce_event_file(self.LOG)
        self.assertEqual(set(r.solver_totals), {"cli-dsh", "reason", "cli-dsh-2"})
        self.assertIn("run-20670", r.challenge_rollups)
        # The rollup is reported but NOT folded into the solver total.
        self.assertEqual(r.challenge_rollups["run-20670"]["input_tokens"], 1099455)


class SnapshotShapeTests(unittest.TestCase):
    def test_result_is_json_serialisable(self):
        r = reduce_usage([cost_event(1, "solver", "a", 5, 1, usd=0.5)])
        text = json.dumps(r.to_dict(), ensure_ascii=False)
        self.assertIn("usage_stats_version", text)

    def test_non_cost_events_are_ignored(self):
        events = [
            {"event_type": "tool.start", "seq": 1, "payload": {}},
            cost_event(2, "solver", "a", 7, 2),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.input_tokens, 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
