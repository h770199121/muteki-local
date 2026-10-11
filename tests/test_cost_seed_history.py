"""Host-run unittest for CostController.seed_history (batch 9, 6D).

A relaunched generation must inherit the pre-restart spend: seeding is
reset-then-seed so repeated relaunches never double-count, and the labs
usage_reduce shim must stay semantically identical to the core module.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "labs" / "nyu-ctf"))

from muteki.core.cost import CostController  # noqa: E402
from muteki.core.usage_reduce import (  # noqa: E402
    USAGE_STATS_VERSION as CORE_VERSION,
    reduce_usage as core_reduce,
)
import usage_reduce as shim  # noqa: E402

SOLVER_TOTALS = {
    "cli-dsh": {"input_tokens": 1000, "output_tokens": 100, "usd": 0.5,
                "execution_generation": 1, "seq": 50},
    "cli-dsh-2": {"input_tokens": 2000, "output_tokens": 200, "usd": 1.0,
                  "execution_generation": 2, "seq": 10},
}
ROLLUPS = {
    "be1": {"input_tokens": 4500, "output_tokens": 450, "usd": 2.25,
            "execution_generation": 2, "seq": 20},
}


class SeedHistoryTests(unittest.TestCase):
    def test_seed_populates_all_scopes(self):
        cost = CostController()
        cost.seed_history(input_tokens=3000, output_tokens=300, usd=1.5,
                          solver_totals=SOLVER_TOTALS,
                          challenge_rollups=ROLLUPS)
        self.assertEqual(cost._global.input_tokens, 3000)
        self.assertEqual(cost._global.tokens, 3300)
        self.assertAlmostEqual(cost._global.usd, 1.5)
        self.assertEqual(set(cost._by_solver), {"cli-dsh", "cli-dsh-2"})
        self.assertEqual(cost._by_solver["cli-dsh-2"].tokens, 2200)
        self.assertEqual(set(cost._by_challenge), {"be1"})
        self.assertAlmostEqual(cost._by_challenge["be1"].usd, 2.25)

    def test_repeated_seeds_never_double_count(self):
        cost = CostController()
        cost.seed_history(input_tokens=3000, output_tokens=300, usd=1.5,
                          solver_totals=SOLVER_TOTALS, challenge_rollups={})
        # second relaunch: history grew, the seed REPLACES the ledgers
        cost.seed_history(input_tokens=5000, output_tokens=500, usd=2.5,
                          solver_totals=SOLVER_TOTALS, challenge_rollups={})
        self.assertEqual(cost._global.input_tokens, 5000)
        self.assertAlmostEqual(cost._global.usd, 2.5)
        self.assertEqual(cost._by_solver["cli-dsh"].input_tokens, 1000)

    def test_empty_history_yields_zero_ledgers(self):
        cost = CostController()
        cost.seed_history(input_tokens=0, output_tokens=0, usd=0.0,
                          solver_totals={}, challenge_rollups={})
        self.assertEqual(cost._global.tokens, 0)
        self.assertEqual(cost._by_solver, {})

    def test_calls_seed_as_zero(self):
        cost = CostController()
        cost.seed_history(input_tokens=10, output_tokens=1, usd=0.0,
                          solver_totals={}, challenge_rollups={})
        self.assertEqual(cost._global.calls, 0)

    def test_shim_matches_core_semantics(self):
        self.assertEqual(shim.USAGE_STATS_VERSION, CORE_VERSION)
        self.assertEqual(shim.USAGE_STATS_VERSION, 3)
        events = [
            {"event_type": "cost.update", "seq": 1, "payload": {
                "scope": "solver", "solver_id": "a",
                "input_tokens": 100, "output_tokens": 10, "usd": 0.0,
                "execution_generation": 1}},
            {"event_type": "cost.update", "seq": 2, "payload": {
                "scope": "solver", "solver_id": "a",
                "input_tokens": 300, "output_tokens": 30, "usd": 0.0,
                "execution_generation": 1}},
        ]
        a, b = core_reduce(events), shim.reduce_usage(events)
        self.assertEqual((a.input_tokens, a.output_tokens),
                         (b.input_tokens, b.output_tokens))
        self.assertEqual(a.basis, b.basis)


if __name__ == "__main__":
    unittest.main()
