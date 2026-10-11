"""Durable interrupted-run recovery helpers.

Stdlib-only so host unittests can exercise the decision logic directly
(apps.web.run_manager imports pydantic via control_adapter and cannot be
imported on the bare host).

Leftover fix (restart auto-recovery): a control-plane restart mid-run leaves
the newest execution generation closed by the durable reconciliation as
run.finished(reason="interrupted").  MUTEKI_AUTO_RESUME lets the operator opt
into re-opening those runs automatically on the next boot through the same
resolve() continuation path the 继续 button uses.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Mapping

from muteki.core.events import EventType


def newest_generation_interrupted(
    rows: Iterable[Mapping[str, Any]], generation: int,
) -> bool:
    """True when ``generation``'s terminal event is the interrupted reconciliation.

    Only terminal events tagged with exactly this execution_generation count: a
    later resolve() opens a new generation whose own terminal (solved / failed
    / budget-exhausted / ...) supersedes the older interrupted closure.
    """
    try:
        generation = int(generation or 0)
    except (TypeError, ValueError):
        return False
    if generation <= 0:
        return False
    terminal = EventType.RUN_FINISHED.value
    reason: "str | None" = None
    for row in rows:
        if str(row.get("event_type") or "") != terminal:
            continue
        payload = row.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        try:
            row_gen = int(payload.get("execution_generation") or 0)
        except (TypeError, ValueError):
            row_gen = 0
        if row_gen == generation:
            reason = str(payload.get("reason") or "")
    return reason == "interrupted"


def auto_resume_enabled(env: "Mapping[str, str] | None" = None) -> bool:
    """MUTEKI_AUTO_RESUME gate — default off (auto relaunch burns budget)."""
    source = env if env is not None else os.environ
    raw = str(source.get("MUTEKI_AUTO_RESUME") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def auto_resume_stagger_s(env: "Mapping[str, str] | None" = None) -> float:
    """Seconds between successive auto-resume launches (boot herd guard)."""
    source = env if env is not None else os.environ
    try:
        value = float(source.get("MUTEKI_AUTO_RESUME_STAGGER_S") or 5.0)
    except (TypeError, ValueError):
        value = 5.0
    return max(0.0, value)
