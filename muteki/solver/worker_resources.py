"""D07 — worker container resource limits.

``container_exec`` already accepts ``memory`` / ``cpus`` / ``pids_limit`` and appends
them to ``docker run``, but every value is optional and NO caller ever passed one:
the single production call site (``coordinator_race``) omitted all three. The
containers therefore ran with no explicit ceiling, on a host whose CPU and RAM are
shared with the local model — an OOM in Ghidra or a large PCAP pass then shows up as
the model slowing down or timing out, which is easy to misread as "the challenge was
hard".

This module resolves the effective limits from one place so the Coordinator path and
the standby path cannot drift apart again.

Deliberate choices
------------------
* **No default ceiling is invented here.** Upstream's ``full`` preset (2GB / 2CPU)
  is upstream's default for its own sizing, and Ghidra/Sage frequently need more
  than 2GB. Shipping it as our default would be a guess dressed as a policy. Limits
  stay unset unless configured, and this module reports that honestly.
* **Unset is a valid, visible state.** :func:`describe_limits` renders it as
  ``unlimited`` so the UI and events can show it rather than implying a bound.
* Validation is defensive: a bad value is rejected with a clear error instead of
  being silently dropped, because a silently dropped limit means an unlimited
  container that the operator believes is capped.

Environment variables (all optional, no secrets):
    MUTEKI_WORKER_MEMORY        docker --memory value, e.g. ``8g``
    MUTEKI_WORKER_CPUS          docker --cpus value, e.g. ``2.0``
    MUTEKI_WORKER_PIDS_LIMIT    integer process cap
    MUTEKI_WORKER_RESOURCES_REQUIRED
        ``1`` turns a malformed value into a hard error at startup instead of a
        warning; anything else degrades to "no limit" with a recorded reason.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

ENV_MEMORY = "MUTEKI_WORKER_MEMORY"
ENV_CPUS = "MUTEKI_WORKER_CPUS"
ENV_PIDS = "MUTEKI_WORKER_PIDS_LIMIT"
ENV_REQUIRED = "MUTEKI_WORKER_RESOURCES_REQUIRED"

# docker accepts forms like 8g / 512m / 1.5g; we only sanity-check the shape.
_MEMORY_RE = re.compile(r"^\d+(?:\.\d+)?\s*[kmgtKMGT]?[bB]?$")
_CPUS_RE = re.compile(r"^\d+(?:\.\d+)?$")


class ResourceConfigError(ValueError):
    """A configured worker resource limit is malformed."""


@dataclass(frozen=True)
class ResourceLimits:
    """Effective limits for worker containers.

    ``None`` means *unset*, which is reported as unlimited — it is not an error and
    not the same as a zero or an empty string.
    """

    memory: str | None = None
    cpus: str | None = None
    pids_limit: int | None = None
    #: Why a configured value was dropped (empty when nothing was rejected).
    warnings: tuple[str, ...] = ()

    @property
    def any_set(self) -> bool:
        return any(v is not None for v in
                   (self.memory, self.cpus, self.pids_limit))

    @property
    def unlimited(self) -> bool:
        return not self.any_set

    def as_docker_args(self) -> list[str]:
        """Render the ``docker run`` flags in the order container_exec expects."""
        args: list[str] = []
        if self.memory:
            args += ["--memory", str(self.memory)]
        if self.cpus:
            args += ["--cpus", str(self.cpus)]
        if self.pids_limit and int(self.pids_limit) > 0:
            args += ["--pids-limit", str(int(self.pids_limit))]
        return args

    def as_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for ``ensure_container``."""
        return {"memory": self.memory, "cpus": self.cpus,
                "pids_limit": self.pids_limit}

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory": self.memory or "unlimited",
            "cpus": self.cpus or "unlimited",
            "pids_limit": self.pids_limit if self.pids_limit else "unlimited",
            "configured": self.any_set,
            "warnings": list(self.warnings),
        }


def _validate_memory(raw: str) -> str:
    value = raw.strip()
    if not _MEMORY_RE.match(value):
        raise ResourceConfigError(
            f"{ENV_MEMORY}={value!r} is not a docker memory value "
            f"(expected forms like 8g, 512m, 1.5g)")
    return value


def _validate_cpus(raw: str) -> str:
    value = raw.strip()
    if not _CPUS_RE.match(value):
        raise ResourceConfigError(
            f"{ENV_CPUS}={value!r} is not a docker cpu count (expected e.g. 2 or 2.0)")
    if float(value) <= 0:
        raise ResourceConfigError(f"{ENV_CPUS}={value!r} must be greater than 0")
    return value


def _validate_pids(raw: str) -> int:
    value = raw.strip()
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ResourceConfigError(
            f"{ENV_PIDS}={value!r} is not an integer") from exc
    if parsed <= 0:
        raise ResourceConfigError(f"{ENV_PIDS}={value!r} must be greater than 0")
    return parsed


def resolve_limits(env: Mapping[str, str] | None = None) -> ResourceLimits:
    """Resolve effective limits from the environment.

    A malformed value is dropped and recorded in ``warnings`` so the container still
    starts — unless ``MUTEKI_WORKER_RESOURCES_REQUIRED=1``, which turns the problem
    into a hard error at startup. Silently dropping a limit is the failure mode D07
    exists to prevent, so it is always at least reported.
    """
    source: Mapping[str, str] = os.environ if env is None else env
    required = str(source.get(ENV_REQUIRED, "") or "").strip() in {"1", "true", "yes"}
    warnings: list[str] = []

    def _resolve(var: str, validator) -> Any:
        raw = str(source.get(var, "") or "").strip()
        if not raw:
            return None
        try:
            return validator(raw)
        except ResourceConfigError as exc:
            if required:
                raise
            warnings.append(str(exc))
            return None

    return ResourceLimits(
        memory=_resolve(ENV_MEMORY, _validate_memory),
        cpus=_resolve(ENV_CPUS, _validate_cpus),
        pids_limit=_resolve(ENV_PIDS, _validate_pids),
        warnings=tuple(warnings),
    )


def describe_limits(limits: ResourceLimits | None) -> str:
    """One-line human summary for logs, events and the settings view."""
    if limits is None:
        return "worker containers: no explicit resource limit (unlimited)"
    parts = []
    if limits.memory:
        parts.append(f"memory={limits.memory}")
    if limits.cpus:
        parts.append(f"cpus={limits.cpus}")
    if limits.pids_limit:
        parts.append(f"pids={limits.pids_limit}")
    # A configured-but-rejected value must surface even when nothing ended up set;
    # otherwise "unlimited" would hide the fact that a limit was asked for and lost.
    body = ", ".join(parts) if parts else "no explicit resource limit (unlimited)"
    text = f"worker containers: {body}"
    if limits.warnings:
        text += f" [ignored: {'; '.join(limits.warnings)}]"
    return text


__all__ = [
    "ResourceLimits",
    "ResourceConfigError",
    "resolve_limits",
    "describe_limits",
    "ENV_MEMORY",
    "ENV_CPUS",
    "ENV_PIDS",
    "ENV_REQUIRED",
]
