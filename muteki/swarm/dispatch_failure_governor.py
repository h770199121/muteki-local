"""D04 — dispatch-failure classification and consecutive-failure governance.

Why this exists
---------------
A worker that never starts looks identical to a worker that is merely slow. Without a
distinction, the Coordinator keeps re-dispatching the same broken configuration until
the wall clock runs out, and the run is eventually reported as "unsolved" — which
reads like a reasoning failure but is really an environment failure.

Upstream solves this in ``coordinator_worker_reap.py``. That file is deliberately NOT
copied here: it depends on ``coordinator_state``, ``runtime_terminal_failure`` and
``_runtime_failure_code/_phase``, none of which exist in this 0.3.2-derived tree
(a direct copy would raise AttributeError). Its *semantics* are reproduced here
against what this tree actually has:

* ``_runtime_process_started`` — the real process-start receipt, already set by
  ``cli_solver`` and already consumed by ``coordinator_race`` to compute ``prestart``.
* ``cli_launch_check.launch_failure_code`` — the deterministic launch-failure
  classifier, including ``worker_spawn_rejected``.

Design decisions
----------------
* **Only pre-start rejections count.** A worker that started and then failed at
  runtime is a different problem (model, target, tool) and is handled by the
  fruitless-interrupt / reflection path already in this tree. Conflating the two
  would stop runs for the wrong reason.
* **A real start receipt clears the streak** — not merely a task being created.
  Otherwise a task that spawns and immediately dies would keep the streak alive and
  trip the limit on a system that is actually working.
* **The threshold is a default, not a decision.** Upstream's 5 is a source value, not
  a validated one for this deployment; it is exposed as configuration and the module
  documents that.
* **No silent clamping.** If the limit is disabled (``<= 0``) the governor is off and
  says so, rather than pretending to protect anything.

Dependency-free so it can be imported and tested without the project venv's missing
third-party packages.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

#: Upstream's value. Kept as the default for continuity, but it is upstream's
#: assumption — set MUTEKI_MAX_CONSECUTIVE_WORKER_FAILURES to suit the deployment.
DEFAULT_MAX_CONSECUTIVE_FAILURES = 5

ENV_MAX_FAILURES = "MUTEKI_MAX_CONSECUTIVE_WORKER_FAILURES"

#: Rejection reasons that mean "this configuration cannot start a process at all".
#: Sourced from the codes cli_launch_check recognises plus the dispatch reasons the
#: Coordinator reports. Anything else is treated as a runtime problem, not a
#: pre-start rejection.
PRESTART_REJECTIONS = frozenset({
    "worker_spawn_rejected",
    "unavailable_profile",
    "worker_selection_failed",
    "unknown_engine",
    "process_input_illegal",
    "process_argv_too_large",
    "worker_environment_unavailable",
    "provider_config_missing",
    "model_catalog_missing",
    "container_unavailable",
    "container_setup_failed",
})

#: Rejections that mean "the system is healthy but currently FULL" (audit 5.1):
#: counting them as fatal pre-start failures would stop runs on a working setup
#: merely because the operator filled the worker pool. They are never counted,
#: even when a caller forces pre-start classification.
CAPACITY_REJECTIONS = frozenset({
    "max_workers",
    "profile_capacity",
})


def resolve_failure_limit(env: Mapping[str, str] | None = None) -> int:
    """Effective consecutive-failure limit. ``<= 0`` disables the governor."""
    source: Mapping[str, str] = os.environ if env is None else env
    raw = str(source.get(ENV_MAX_FAILURES, "") or "").strip()
    if not raw:
        return DEFAULT_MAX_CONSECUTIVE_FAILURES
    try:
        return int(raw)
    except ValueError:
        # A malformed limit must not silently disable the governor, and must not
        # crash the Coordinator either: fall back to the documented default.
        return DEFAULT_MAX_CONSECUTIVE_FAILURES


def is_prestart_rejection(reason: str | None) -> bool:
    """True when a dispatch rejection happened BEFORE any process could start."""
    code = str(reason or "").strip()
    if not code:
        return False
    if is_capacity_rejection(code):
        # "healthy but full" — including a qualified form whose tail is capacity
        # (worker_spawn_rejected:max_workers) — is never a failure streak.
        return False
    if code in PRESTART_REJECTIONS:
        return True
    # A qualified code such as "worker_spawn_rejected:unavailable_profile" also counts.
    head, _, tail = code.partition(":")
    if head.strip() in PRESTART_REJECTIONS:
        if tail.strip() and is_capacity_rejection(tail):
            return False
        return True
    return False


def is_capacity_rejection(reason: str | None) -> bool:
    """True when the rejection means 'healthy but full' — never a failure streak."""
    code = str(reason or "").strip()
    if not code:
        return False
    if code in CAPACITY_REJECTIONS:
        return True
    head, _, tail = code.partition(":")
    if head.strip() in CAPACITY_REJECTIONS:
        return True
    return bool(tail.strip()) and tail.strip() in CAPACITY_REJECTIONS


@dataclass
class FailureGovernor:
    """Counts consecutive pre-start dispatch failures and decides when to stop.

    ``record_start_observed`` must be called with a REAL process-start receipt. It is
    the only thing that clears the streak.
    """

    limit: int = DEFAULT_MAX_CONSECUTIVE_FAILURES
    consecutive: int = 0
    #: engine -> last rejection detail, so the stop reason names the actual cause.
    last_detail: str = ""
    last_engine: str = ""
    limit_reached: bool = False
    #: Set once a start is observed, so a later failure starts a fresh streak.
    _start_seen: bool = False
    #: Worker ids whose process-start receipt was already consumed (audit 5.1: a
    #: long-lived live solver must not re-clear the streak on every later
    #: rejection — only NEW start receipts count).
    credited_workers: set[str] = field(default_factory=set)
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.limit > 0

    def credit_start(self, worker: str = "") -> bool:
        """Consume one NEW process-start receipt. Returns True when it was new.

        A worker id already credited returns False without touching the streak:
        repeatedly observing the same live solver must not keep resetting the
        failure counter, or the limit can never be reached.
        """
        sid = str(worker or "")
        if not sid or sid in self.credited_workers:
            return False
        self.credited_workers.add(sid)
        self.record_start_observed(sid)
        return True

    def record_start_observed(self, worker: str = "") -> int:
        """Clear the streak on a real process start. Returns the previous streak.

        Returns 0 when nothing was pending, so callers can skip emitting a
        recovery event on the common path.
        """
        previous = self.consecutive
        self.consecutive = 0
        self._start_seen = True
        if previous:
            self.history.append({"event": "recovered", "worker": worker,
                                 "previous_consecutive_failures": previous})
        return previous

    def record_failure(self, *, worker: str, engine: str, detail: str,
                       reason: str, force: bool = False) -> bool:
        """Count one pre-start rejection. Returns True when the limit is reached.

        ``force`` marks a rejection the caller has already proven happened before
        any process could start (auto-dispatch spawn sites and pre-start worker
        deaths emit free-text reasons, not the classified codes). Capacity
        rejections are never counted, forced or not: a healthy-but-full system is
        not a broken configuration (audit 5.1).
        """
        if not self.enabled:
            return False
        if is_capacity_rejection(reason):
            return False
        if not force and not is_prestart_rejection(reason):
            # Runtime failure: explicitly NOT counted. The fruitless-interrupt path
            # owns that case; counting it here would stop healthy-but-unlucky runs.
            return False

        self.consecutive += 1
        self.last_detail = str(detail or reason)[:300]
        self.last_engine = str(engine or "")
        self.history.append({
            "event": "dispatch_failed", "worker": worker, "engine": engine,
            "consecutive_failures": self.consecutive,
            "stop_after": self.limit, "reason": reason, "detail": self.last_detail,
        })

        if self.consecutive >= self.limit:
            if not self.limit_reached:
                self.limit_reached = True
                self.history.append({
                    "event": "limit_reached",
                    "consecutive_failures": self.consecutive,
                    "stop_after": self.limit,
                    "detail": self.last_detail,
                })
            return True
        return False

    def remaining(self) -> int | None:
        """Failures left before the limit, or None when disabled/already reached."""
        if not self.enabled or self.limit_reached:
            return None
        return max(0, self.limit - self.consecutive)

    def stop_reason(self) -> str:
        """Operator-facing explanation, naming the real cause rather than a count."""
        if not self.limit_reached:
            return ""
        return (f"{self.consecutive} consecutive Worker dispatches failed before "
                f"process start (engine={self.last_engine or 'unknown'}): "
                f"{self.last_detail}")

    def failure_code(self) -> str:
        """Stable code for the runtime-failure record, matching upstream's naming."""
        return "consecutive_worker_dispatch_failures"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "limit": self.limit,
            "consecutive_failures": self.consecutive,
            "limit_reached": self.limit_reached,
            "remaining": self.remaining(),
            "last_engine": self.last_engine,
            "last_detail": self.last_detail,
            "stop_reason": self.stop_reason(),
            "failure_code": self.failure_code() if self.limit_reached else "",
        }


def worker_is_prestart(solver: Any) -> bool:
    """Whether a solver object represents a worker that never reached process start.

    Mirrors the ``prestart`` computation already used in ``coordinator_race``: no
    process-start receipt AND no control-context delivery crossing the boundary. A
    solver whose context was actually delivered must not be treated as pre-start —
    the operator's instruction already reached the runtime.
    """
    process_started = bool(getattr(solver, "_runtime_process_started", True))
    crossed = bool(
        getattr(solver, "_control_context_delivery_committed", False)
        or getattr(solver, "_control_context_delivery_unknown", False)
    )
    return not process_started and not crossed


def summarize_active_solvers(solvers: Iterable[Any]) -> dict[str, int]:
    """Count active solvers by start state, for the health/event payload."""
    summary = {"total": 0, "started": 0, "prestart": 0}
    for solver in solvers:
        if getattr(solver, "done", None) and solver.done():
            continue
        summary["total"] += 1
        if worker_is_prestart(solver):
            summary["prestart"] += 1
        else:
            summary["started"] += 1
    return summary


__all__ = [
    "DEFAULT_MAX_CONSECUTIVE_FAILURES",
    "ENV_MAX_FAILURES",
    "PRESTART_REJECTIONS",
    "CAPACITY_REJECTIONS",
    "FailureGovernor",
    "is_capacity_rejection",
    "is_prestart_rejection",
    "resolve_failure_limit",
    "summarize_active_solvers",
    "worker_is_prestart",
]
