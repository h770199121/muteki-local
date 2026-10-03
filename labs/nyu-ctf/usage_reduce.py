"""A01 — usage reduction for evaluation accounting.

The evaluation harness used to sum every ``cost.update`` event:

    tokens_in = sum(p["input_tokens"] for p in cost_events)

Those events are CUMULATIVE SNAPSHOTS, not deltas, and they arrive at two scopes
(``solver`` and ``challenge``).  Summing them therefore double-counts each solver
across its own successive snapshots AND adds the challenge rollup on top of the
solvers it already contains.  For run-20670 the naive sum reported
6,312,289 / 185,575 input/output, while the solvers' own final ledgers account for
1,563,948 / 52,737.

This module is the single reduction entry point.  Rules:

* group by (scope, identity) and keep only the LAST snapshot in each group;
* never add a challenge-scope rollup to the solver ledgers it covers;
* report which solvers are covered by a challenge rollup, and whether the
  reconstruction is complete;
* when the history cannot be rebuilt unambiguously, say so instead of emitting a
  precise-looking total.

It is deliberately dependency-free so it can be imported and tested without the
project venv's missing third-party packages.

Run:  python -X utf8 -B -m unittest tests.test_usage_reduce -v
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

# Bump when the reduction semantics change, so stored results stay interpretable.
USAGE_STATS_VERSION = 2

COST_EVENT_TYPES = frozenset({"cost.update", "cost_update"})

SCOPE_SOLVER = "solver"
SCOPE_CHALLENGE = "challenge"
SCOPE_RUN = "run"


@dataclass(frozen=True)
class UsageSnapshot:
    """One cumulative usage snapshot from a single accounting scope."""

    input_tokens: int
    output_tokens: int
    usd: float
    scope: str
    identity: str
    execution_generation: int
    seq: int

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> "UsageSnapshot | None":
        if (event.get("event_type") or "") not in COST_EVENT_TYPES:
            return None
        payload = event.get("payload") or {}
        scope = str(payload.get("scope") or "").strip()
        solver_id = payload.get("solver_id")
        challenge_id = payload.get("challenge_id")

        if not scope:
            # Fall back to the shape, but only when the signal is unambiguous.
            if solver_id:
                scope = SCOPE_SOLVER
            elif challenge_id:
                scope = SCOPE_CHALLENGE
            else:
                scope = SCOPE_RUN

        if scope == SCOPE_SOLVER:
            identity = str(solver_id or "")
        elif scope == SCOPE_CHALLENGE:
            identity = str(challenge_id or "")
        else:
            identity = str(payload.get("run_id") or event.get("run_id") or "")

        return cls(
            input_tokens=int(payload.get("input_tokens") or 0),
            output_tokens=int(payload.get("output_tokens") or 0),
            usd=float(payload.get("usd") or 0.0),
            scope=scope,
            identity=identity,
            execution_generation=int(payload.get("execution_generation") or 0),
            seq=int(event.get("seq") or 0),
        )


@dataclass
class UsageReduction:
    """Reduced usage plus an honest account of what it does and does not cover."""

    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0

    stats_version: int = USAGE_STATS_VERSION

    #: solver identity -> its own final cumulative snapshot
    solver_totals: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: challenge identity -> final challenge-scope rollup (NOT added to solvers)
    challenge_rollups: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_rollup: dict[str, Any] | None = None

    #: solvers that a challenge rollup already accounts for
    solvers_covered_by_rollup: list[str] = field(default_factory=list)
    #: solvers that only ever appear through a challenge rollup
    solvers_rollup_only: list[str] = field(default_factory=list)

    basis: str = "none"           # solver_ledgers | challenge_rollup | none
    telemetry_complete: bool = True
    incomplete_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usd": round(self.usd, 6),
            "usage_stats_version": self.stats_version,
            "basis": self.basis,
            "telemetry_complete": self.telemetry_complete,
            "incomplete_reasons": sorted(set(self.incomplete_reasons)),
            "solver_totals": self.solver_totals,
            "challenge_rollups": self.challenge_rollups,
            "run_rollup": self.run_rollup,
            "solvers_covered_by_rollup": sorted(self.solvers_covered_by_rollup),
            "solvers_rollup_only": sorted(self.solvers_rollup_only),
        }


def _newer(current: UsageSnapshot, candidate: UsageSnapshot) -> bool:
    """Prefer the later generation, then the higher sequence.

    Ordering matters after a resume: a restarted execution generation restarts the
    accumulation, so the highest (generation, seq) is the authoritative snapshot.
    """
    return (candidate.execution_generation, candidate.seq) > (
        current.execution_generation, current.seq)


def reduce_usage(events: Iterable[dict[str, Any]]) -> UsageReduction:
    """Reduce cumulative usage snapshots to one non-double-counted figure.

    ``events`` is any iterable of decoded event dicts (order-insensitive except that
    ties are broken by ``seq``).  Duplicates are harmless.
    """
    latest: dict[tuple[str, str], UsageSnapshot] = {}

    for event in events:
        snap = UsageSnapshot.from_event(event)
        if snap is None:
            continue
        key = (snap.scope, snap.identity)
        current = latest.get(key)
        if current is None or _newer(current, snap):
            latest[key] = snap

    result = UsageReduction()

    solver_snaps = [s for (sc, _), s in latest.items() if sc == SCOPE_SOLVER]
    challenge_snaps = [s for (sc, _), s in latest.items() if sc == SCOPE_CHALLENGE]
    run_snaps = [s for (sc, _), s in latest.items() if sc == SCOPE_RUN]

    for snap in solver_snaps:
        result.solver_totals[snap.identity] = {
            "input_tokens": snap.input_tokens,
            "output_tokens": snap.output_tokens,
            "usd": round(snap.usd, 6),
            "execution_generation": snap.execution_generation,
            "seq": snap.seq,
        }

    for snap in challenge_snaps:
        result.challenge_rollups[snap.identity] = {
            "input_tokens": snap.input_tokens,
            "output_tokens": snap.output_tokens,
            "usd": round(snap.usd, 6),
            "execution_generation": snap.execution_generation,
            "seq": snap.seq,
        }

    if run_snaps:
        snap = run_snaps[0]
        result.run_rollup = {
            "input_tokens": snap.input_tokens,
            "output_tokens": snap.output_tokens,
            "usd": round(snap.usd, 6),
            "execution_generation": snap.execution_generation,
            "seq": snap.seq,
        }

    if solver_snaps:
        # Solver ledgers are the finest-grained authoritative source: every solver
        # reports its own total, so summing the per-solver FINAL values neither
        # double-counts snapshots nor mixes in a rollup.
        result.basis = "solver_ledgers"
        result.input_tokens = sum(int(v["input_tokens"]) for v in result.solver_totals.values())
        result.output_tokens = sum(int(v["output_tokens"]) for v in result.solver_totals.values())
        result.usd = sum(float(v["usd"]) for v in result.solver_totals.values())

        # A challenge rollup that is >= the solver total clearly subsumes it, so
        # report the overlap instead of adding the two together.
        rollup_total_in = sum(int(v["input_tokens"]) for v in result.challenge_rollups.values())
        if result.challenge_rollups and rollup_total_in <= result.input_tokens:
            result.solvers_covered_by_rollup = sorted(result.solver_totals)
            result.telemetry_complete = False
            result.incomplete_reasons.append(
                "challenge rollup overlaps solver ledgers; some solver usage is "
                "only visible through the rollup, so solver ledgers understate the "
                "true total")
    elif challenge_snaps:
        result.basis = "challenge_rollup"
        result.input_tokens = sum(int(v["input_tokens"]) for v in result.challenge_rollups.values())
        result.output_tokens = sum(int(v["output_tokens"]) for v in result.challenge_rollups.values())
        result.usd = sum(float(v["usd"]) for v in result.challenge_rollups.values())
    elif run_snaps:
        result.basis = "challenge_rollup"
        rollup = result.run_rollup or {}
        result.input_tokens = int(rollup.get("input_tokens") or 0)
        result.output_tokens = int(rollup.get("output_tokens") or 0)
        result.usd = float(rollup.get("usd") or 0.0)
    else:
        result.basis = "none"
        result.telemetry_complete = False
        result.incomplete_reasons.append("no cost.update events found")

    return result


def read_events(path: str | Path) -> list[dict[str, Any]]:
    """Read an NDJSON event log, skipping undecodable lines."""
    events: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                decoded = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                events.append(decoded)
    return events


def iter_events(path: str | Path) -> Iterator[dict[str, Any]]:
    """Streaming variant for large logs."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                decoded = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                yield decoded


def reduce_event_file(path: str | Path) -> UsageReduction:
    return reduce_usage(iter_events(path))


__all__ = [
    "USAGE_STATS_VERSION",
    "UsageReduction",
    "UsageSnapshot",
    "read_events",
    "iter_events",
    "reduce_usage",
    "reduce_event_file",
]
