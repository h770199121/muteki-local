"""Batch 9 container acceptance (runs INSIDE the web-api container via uv).

A3 auto-resume wiring, verified live 2026-10-11 against the rebuilt
muteki-web:latest (container py == repo HEAD, diff=0):

    docker exec -i muteki-local-web-api-1 uv run python - < tests/container_batch9_auto_resume_wiring.py

Chain under test: synthetic frozen run (newest generation closed as
interrupted) -> _rehydrate candidate collection -> continuation cost seeding
(reduce_usage v3 + CostController.seed_history) -> schedule_auto_resume ->
resolve() (monkeypatched — never launches a real swarm) -> MUTEKI_AUTO_RESUME
flag gate. Real runs: ALL PASS (4/4).
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/app")
os.environ["MUTEKI_AUTO_RESUME"] = "1"

tmp = Path(tempfile.mkdtemp(prefix="a3probe-"))
rid = "run-90001"
CH = {"name": "probe", "category": "web", "expected_flags": 1, "multi_flag": False}
# NB: every event needs the top-level run_id — SessionStore.load_all drops
# rows without it (this cost the first acceptance run one debug cycle).
lines = [
    {"event_type": "run.preparing", "seq": 1, "ts": 1.0, "run_id": rid,
     "payload": {"challenge": CH}},
    {"event_type": "run.started", "seq": 2, "ts": 2.0, "run_id": rid,
     "solver_id": "cli-dsh",
     "payload": {"scope": "worker", "challenge": CH}},
    {"event_type": "cost.update", "seq": 3, "ts": 3.0, "run_id": rid,
     "payload": {"scope": "solver", "solver_id": "cli-dsh",
                 "input_tokens": 5000, "output_tokens": 500, "usd": 0.0,
                 "execution_generation": 1}},
    {"event_type": "run.finished", "seq": 4, "ts": 4.0, "run_id": rid,
     "payload": {"reason": "interrupted", "solved": False,
                 "flag": None, "flags": [], "expected_flags": 1,
                 "multi_flag": False,
                 "execution_generation": 1,
                 "failure_detail": "probe: control plane restarted while "
                                   "generation 1 was active"}},
]
(tmp / f"{rid}.jsonl").write_text(
    "\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")

from apps.web.run_manager import RunManager  # noqa: E402
from muteki.core.usage_reduce import reduce_usage  # noqa: E402

mgr = RunManager(sessions_root=str(tmp))
got = list(mgr._pending_auto_resume)
assert got == [rid], f"candidates mismatch: {got}"
print("PASS 1/4 rehydrate candidate collection:", got)

run = mgr.get(rid)
assert run is not None and run.started
usage = reduce_usage(run.store.load_all(rid))
assert usage.input_tokens == 5000, usage.to_dict()
assert usage.basis == "solver_ledgers", usage.basis
run.cost.seed_history(input_tokens=usage.input_tokens,
                      output_tokens=usage.output_tokens, usd=usage.usd,
                      solver_totals=usage.solver_totals,
                      challenge_rollups=usage.challenge_rollups)
assert run.cost._global.input_tokens == 5000
assert run.cost._by_solver["cli-dsh"].input_tokens == 5000
print("PASS 2/4 continuation cost seed: basis=%s in=%d"
      % (usage.basis, run.cost._global.input_tokens))

calls = []


async def fake_resolve(run_id, body=None):
    calls.append(run_id)
    return True


mgr.resolve = fake_resolve  # wiring probe: never launch a real swarm


async def main():
    scheduled = mgr.schedule_auto_resume()
    assert scheduled == 1, scheduled
    await mgr._auto_resume_task
    assert calls == [rid], calls
asyncio.run(main())
print("PASS 3/4 schedule_auto_resume -> resolve():", calls)

os.environ["MUTEKI_AUTO_RESUME"] = "0"
mgr2 = RunManager(sessions_root=str(tmp))
assert len(mgr2._pending_auto_resume) == 1
assert mgr2.schedule_auto_resume() == 0
del os.environ["MUTEKI_AUTO_RESUME"]
mgr3 = RunManager(sessions_root=str(tmp))
assert mgr3.schedule_auto_resume() == 0
print("PASS 4/4 flag gate: off/absent -> nothing scheduled")

print("A3 WIRING ACCEPTANCE: ALL PASS")
