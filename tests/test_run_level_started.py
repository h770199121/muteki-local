"""Host-run unittest for muteki.core.events.run_level_started.

Pins the run.started analysis convention (2026-10-04 timing-audit quirk):
worker paths reuse RUN_STARTED with solver_id + scope:"worker", a solver-free
emission is often absent, so analyses take the first solver-free event and fall
back to the earliest — never the last (mid-run redispatch appends workers).
"""

from __future__ import annotations

import unittest

from muteki.core.events import run_level_started


def started(seq, solver_id=None, scope=None):
    payload = {"scope": scope} if scope else {}
    return {"event_type": "run.started", "seq": seq,
            "solver_id": solver_id, "payload": payload}


class RunLevelStartedTests(unittest.TestCase):
    def test_solver_free_event_is_preferred(self):
        events = [started(6, "cli-dsh", "worker"),
                  started(9),
                  started(115, "cli-dsh-2", "worker")]
        self.assertEqual(run_level_started(events)["seq"], 9)

    def test_fallback_takes_earliest_worker_start(self):
        events = [started(6, "cli-dsh", "worker"),
                  started(115, "cli-dsh-2", "worker")]
        self.assertEqual(run_level_started(events)["seq"], 6)

    def test_never_takes_the_last_worker_start(self):
        events = [started(6, "cli-dsh", "worker"),
                  started(234, "cli-dsh-3", "worker")]
        self.assertEqual(run_level_started(events)["seq"], 6)

    def test_worker_scope_tag_excludes_even_without_solver_id(self):
        events = [started(6, None, "worker"), started(7)]
        self.assertEqual(run_level_started(events)["seq"], 7)

    def test_empty_stream_is_none(self):
        self.assertIsNone(run_level_started([]))
        self.assertIsNone(run_level_started(
            [{"event_type": "run.finished", "payload": {}}]))

    def test_accepts_event_models(self):
        from muteki.core.events import Event, EventType
        first = Event(event_type=EventType.RUN_STARTED, run_id="r", seq=6,
                      solver_id="cli-dsh", payload={"scope": "worker"})
        second = Event(event_type=EventType.RUN_STARTED, run_id="r", seq=115,
                       solver_id="cli-dsh-2", payload={"scope": "worker"})
        out = run_level_started([first, second])
        self.assertEqual(out["seq"], 6)
        self.assertEqual(out["solver_id"], "cli-dsh")


if __name__ == "__main__":
    unittest.main()
