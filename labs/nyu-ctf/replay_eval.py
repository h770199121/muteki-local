"""D10 — replay archived runs into the UNIFIED evaluation schema.

The historical ``results.jsonl`` rows mix two reducer versions and two verdict
eras, and ``results-eval-v2.jsonl`` carried a reduced 9-field schema. This tool
regenerates a comparable, versioned results file straight from the original
event streams, so old runs stay usable under the current judge without touching
any archive:

  * A01 usage reduction (current solver-ledger semantics + rollup coverage);
  * A02 evidence verdict (official flag when known, gate fallback otherwise —
    the same ``_eval_solved`` routing the live harness uses);
  * full verdict schema (evidence links, unlinked flags, attempt matching);
  * ``replayed_at`` + reducer/verdict version stamps — never pretend a replay
    is a live record.

Run:
  python -X utf8 -B labs/nyu-ctf/replay_eval.py \
      --source labs/nyu-ctf/results.jsonl \
      --out labs/nyu-ctf/results-eval-v3.jsonl \
      [--only tag-prefix1,tag-prefix2] [--sessions data/sessions]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from eval_verdict import evaluate_attempt  # noqa: E402
from usage_reduce import USAGE_STATS_VERSION, reduce_usage  # noqa: E402

RUN_ID_RE = re.compile(r"run-[A-Za-z0-9_-]{1,64}")


def _load_events(sessions: Path, run_id: str) -> list[dict]:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError(f"bad run id: {run_id!r}")
    path = sessions / f"{run_id}.jsonl"
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _run_level_started(events: list[dict]) -> dict | None:
    """The RUN-level started event, not the worker-level duplicate.

    The coordinator emits ``run.started`` for the run (no solver_id) AND the
    worker path reuses the same event type with ``solver_id`` set (batch-4-1:
    such events now carry ``scope:"worker"``; older streams only distinguish
    by solver_id). Take the first event with no solver_id, falling back to the
    earliest of any kind for old streams.
    """
    started = [e for e in events
               if (e.get("event_type") or "") == "run.started"]
    if not started:
        return None
    run_level = [e for e in started
                 if not str(e.get("solver_id") or "").strip()
                 and (e.get("payload") or {}).get("scope") != "worker"]
    return (run_level or started)[0]


def _gate_solved(events: list[dict]) -> bool:
    return any(
        (e.get("payload") or {}).get("solved") is True
        for e in events
        if (e.get("event_type") or "") in ("run.finished", "RUN_FINISHED")
    )


def _gate_flag(events: list[dict]) -> str | None:
    fins = [e for e in events
            if (e.get("event_type") or "") in ("run.finished", "RUN_FINISHED")]
    return (fins[-1].get("payload") or {}).get("flag") if fins else None


def replay(source: Path, sessions: Path, out: Path,
           only: list[str] | None = None) -> int:
    rows = []
    for i, l in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not l.strip():
            continue
        try:
            rows.append(json.loads(l))
        except json.JSONDecodeError as exc:
            print(f"skip malformed source row {i} ({exc}): {l[:100]!r}",
                  file=sys.stderr)
    if only:
        rows = [r for r in rows
                if any(str(r.get("tag", "")).startswith(p) for p in only)]
    written = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            run_id = str(row.get("run_id") or "")
            path = sessions / f"{run_id}.jsonl"
            if not path.is_file():
                print(f"skip {run_id}: no event stream", file=sys.stderr)
                continue
            events = _load_events(sessions, run_id)
            usage = reduce_usage(events)
            gate_solved = _gate_solved(events)
            # Replays have no official-flag binding change: the challenge entry's
            # flag is whatever the archived row's challenge had — but archived
            # rows do not carry it, so the gate/official distinction collapses to
            # the gate for replay rows whose flag was empty and to the evidence
            # verdict otherwise. We conservatively report BOTH and mark the
            # basis; consumers must not mix them.
            verdict = evaluate_attempt(
                events, expected_flags=[],
                attempt=((row.get("env_binding") or {}).get("attempt")),
                artifacts_dir=str(sessions / run_id / "workspace" / "arts"))
            record = {
                "tag": row.get("tag"), "engine": row.get("engine"),
                "challenge": row.get("challenge"), "run_id": run_id,
                "finished": row.get("finished"),
                "elapsed_s": row.get("elapsed_s"),
                "wall_budget_s": row.get("wall_budget_s"),
                "tool_calls": row.get("tool_calls"),
                "gate_solved": gate_solved,
                "gate_flag": _gate_flag(events),
                "eval_verdict": verdict.to_dict(),
                "usage_stats_version": USAGE_STATS_VERSION,
                "usage_basis": usage.basis,
                "tokens_in": usage.input_tokens,
                "tokens_out": usage.output_tokens,
                "usage_telemetry_complete": usage.telemetry_complete,
                "usage_incomplete_reasons": usage.incomplete_reasons,
                # Batch-4-1: a replayed run keeps the env binding recorded by
                # the live harness when the archived row carries one — do not
                # silently drop it in favor of the replay-time environment.
                "env_binding": row.get("env_binding"),
                "events": len(events),
                "replayed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "replay_note": (
                    "replay 口径：expected_flags 为空时由 gate-derived flag 走同一条"
                    "证据管线（须回查真实 tool.result 输出）；solved=verdict.solved，"
                    "gate_solved/gate_flag 为披露字段；框架纯耗时见 framework_span_s"),
            }
            started = _run_level_started(events)
            fins = [e for e in events
                    if (e.get("event_type") or "") == "run.finished"]
            if started and fins:
                record["framework_span_s"] = round(
                    fins[-1]["ts"] - started["ts"], 1)
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    print(f"replayed {written} runs -> {out}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(HERE / "results.jsonl"))
    ap.add_argument("--out", default=str(HERE / "results-eval-v3.jsonl"))
    ap.add_argument("--sessions",
                    default=str(HERE.parents[1] / "data" / "sessions"))
    ap.add_argument("--only", default="",
                    help="comma-separated tag prefixes to include")
    args = ap.parse_args()
    only = [p for p in args.only.split(",") if p.strip()]
    return replay(Path(args.source), Path(args.sessions), Path(args.out),
                  only or None)


if __name__ == "__main__":
    sys.exit(main())
