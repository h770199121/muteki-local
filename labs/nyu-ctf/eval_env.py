"""D10 — freeze the evaluation environment into a verifiable binding.

A score line without its conditions cannot be reproduced or compared. This module
captures, at run time, the identity of everything that influences a run:

  * source:     git commit + dirty flag of the workspace (best-effort)
  * worker:     image reference + image ID (from the env + docker inspect)
  * models:     planner/titler profile and every enabled seat, from the live
                worker config (model + base_url per seat)
  * skills:     SHA-256 of every file under the projected skill sources
  * budget/attempt parameters passed by the caller

Every block is failure-tolerant: an unavailable probe becomes
``{"status": "unavailable", "reason": ...}`` instead of crashing the run or
fabricating a value. Dependency-free.

Run:  python -X utf8 -B -m unittest tests.test_eval_env -v
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WORKER_CONFIG = ROOT / "data" / "sessions" / "_worker_config.json"
SKILL_SOURCES = ROOT / "skills" / "kali-claw-kb"


def _git(args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(ROOT), capture_output=True, text=True,
            timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip()


def _git_block() -> dict[str, Any]:
    commit = _git(["rev-parse", "HEAD"])
    if commit is None:
        return {"status": "unavailable", "reason": "git rev-parse failed"}
    dirty = bool(_git(["status", "--porcelain", "-uno"]))
    return {"status": "ok", "commit": commit, "dirty": dirty}


def _worker_image_block() -> dict[str, Any]:
    ref = os.environ.get("MUTEKI_WORKER_IMAGE", "").strip()
    if not ref:
        return {"status": "unavailable", "reason": "MUTEKI_WORKER_IMAGE not set"}
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", "-f", "{{.Id}}", ref],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable", "reason": "docker inspect failed",
                "ref": ref}
    if proc.returncode != 0:
        return {"status": "unavailable", "reason": "image not present locally",
                "ref": ref}
    return {"status": "ok", "ref": ref, "image_id": (proc.stdout or "").strip()}


def _model_block() -> dict[str, Any]:
    try:
        cfg = json.loads(WORKER_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "unavailable", "reason": f"worker config unreadable: {exc}"}
    planner = cfg.get("llm_profiles", {}).get("planner", {}) or {}
    seats = []
    for seat in cfg.get("seats", []) or []:
        if not seat.get("enabled", False):
            continue
        seats.append({
            "id": seat.get("id"), "engine": seat.get("engine"),
            "model": seat.get("model"),
        })
    profiles = []
    for p in cfg.get("worker_profiles", []) or []:
        if not p.get("enabled", False):
            continue
        profiles.append({
            "id": p.get("id"), "engine": p.get("engine"),
            "model": p.get("model"), "base_url": p.get("base_url"),
        })
    return {
        "status": "ok",
        "planner": {"base_url": planner.get("base_url"),
                    "model": planner.get("model")},
        "enabled_seats": seats,
        "enabled_profiles": profiles,
    }


def _skill_block() -> dict[str, Any]:
    if not SKILL_SOURCES.is_dir():
        return {"status": "unavailable",
                "reason": f"skill source missing: {SKILL_SOURCES}"}
    files: dict[str, str] = {}
    for p in sorted(SKILL_SOURCES.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(SKILL_SOURCES).as_posix()
        digest = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        files[rel] = digest.hexdigest()
    if not files:
        return {"status": "unavailable", "reason": "skill source is empty"}
    return {"status": "ok", "source": str(SKILL_SOURCES), "files_sha256": files}


def freeze_eval_env(*, budget_s: int | None = None,
                    attempt: int | None = None) -> dict[str, Any]:
    """Capture the run-time evaluation environment as a JSON-safe dict."""
    return {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git": _git_block(),
        "worker_image": _worker_image_block(),
        "models": _model_block(),
        "skills": _skill_block(),
        "budget_s": budget_s,
        "attempt": attempt,
    }


__all__ = ["freeze_eval_env"]
