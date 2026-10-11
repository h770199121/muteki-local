"""Back-compat shim — usage reduction moved to muteki.core (batch 9, 6D).

The module is dependency-free stdlib, and core budget seeding (RunManager
continuation relaunch) now needs it; labs/nyu-ctf keeps this shim so archived
analyses and the existing test suite import unchanged. All semantics live in
``muteki/core/usage_reduce.py`` — do not extend the shim.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from muteki.core.usage_reduce import (  # noqa: E402,F401
    USAGE_STATS_VERSION,
    UsageReduction,
    UsageSnapshot,
    iter_events,
    read_events,
    reduce_event_file,
    reduce_usage,
)

__all__ = [
    "USAGE_STATS_VERSION",
    "UsageReduction",
    "UsageSnapshot",
    "read_events",
    "iter_events",
    "reduce_usage",
    "reduce_event_file",
]
