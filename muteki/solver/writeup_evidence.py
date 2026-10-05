"""Writeup evidence — build a verifiable evidence manifest for a finished run.

Batch 4-2 (audit §4): a writeup must cite screenshots and raw outputs that
actually exist. This module turns a run's event stream plus its workspace
artifact stores into a deterministic manifest:

  ``http_interactions``  every tool.result whose output looks like an HTTP
                         response (heuristic: HTTP header / <html), with URL
                         when the paired command carries one;
  ``flag_page``          the interaction whose output contains the accepted
                         flag (if any);
  ``screenshots``        filled in by the HOST-side collector
                         (labs/nyu-ctf/writeup_evidence.py) which replays the
                         key GETs through a real browser while the target is
                         still alive — the web container has no browser;
  ``artifacts``          every artifact file under ``workspace/arts``.

Pure stdlib. Used by the web endpoint (manifest only) and the host collector
(manifest + screenshots).

Run:  python -X utf8 -B -m unittest tests.test_writeup_evidence -v
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

_URL_RE = re.compile(r"https?://[^\s'\"<>]+")
_HTTPISH_RE = re.compile(
    r"^(?:HTTP/|<!DOCTYPE|<html)|<html[\s>]", re.IGNORECASE)
_FLAG_RE = re.compile(r"[A-Za-z0-9_]{2,16}\{[A-Za-z0-9_-]{6,64}\}")


def _output_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        condensed = result.get("condensed")
        if isinstance(condensed, str):
            return condensed
        return ""
    if isinstance(result, str):
        return result
    out = payload.get("output")
    return out if isinstance(out, str) else ""


def _extract_url(command: str) -> str:
    """Pull the first URL from a raw shell line, stripping shell noise.

    URLs parsed out of multi-line curl commands carry trailing line
    continuations (``\\``), quotes and statement separators — the replay and
    the writeup both need the clean URL.
    """
    match = _URL_RE.search(command or "")
    if not match:
        return ""
    url = match.group(0)
    url = url.split("\\n", 1)[0]
    return url.rstrip("\\;,\"'").rstrip("\\")


def _tool_interactions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair tool.start commands with tool.result outputs.

    Batch 5E (audit §4.4): pairing is PER WORKER (solver_id) FIFO — a global
    queue mis-pairs interleaved multi-worker requests (A→response B). The
    solver_id travels top-level on the event; unknown senders share a fallback
    queue so legacy shapes still pair.
    """
    pending: dict[str, list[str]] = {}
    fallback: list[str] = []
    out: list[dict[str, Any]] = []

    def _pop(queue_key: str) -> str:
        queue = pending.get(queue_key)
        if queue:
            return queue.pop(0)
        if fallback:
            return fallback.pop(0)
        return ""

    for event in events:
        etype = str(event.get("event_type") or "")
        payload = event.get("payload") or {}
        solver = str(event.get("solver_id") or "") or "_anon"
        if etype == "tool.start":
            command = str(payload.get("tool") or "")
            command = command[6:] if command.startswith("bash: ") else command
            pending.setdefault(solver, []).append(command)
            fallback.append(command)
        elif etype == "tool.result":
            command = _pop(solver)
            text = _output_text(payload)
            if not text:
                continue
            method = ("POST" if re.search(
                r"-X\s*POST|--data(?:-raw)?(?:\s|=)|-d\s", command or "")
                else "GET")
            out.append({
                "seq": int(event.get("seq") or 0),
                "worker": solver,
                "command": command[:500],
                "url": _extract_url(command),
                "method": method,
                "output_head": text[:2000],
                "output_len": len(text),
                "is_http": bool(_HTTPISH_RE.search(text)),
                "sha256": hashlib.sha256(
                    text.encode("utf-8", errors="replace")).hexdigest(),
            })
    return out


def build_evidence_manifest(
    events: list[dict[str, Any]],
    *,
    workspace: Path,
    flag: str | None = None,
) -> dict[str, Any]:
    """Build the writeup evidence manifest for one finished run."""
    interactions = _tool_interactions(events)
    flag_value = flag or ""
    if not flag_value:
        for event in events:
            if str(event.get("event_type") or "") == "run.finished":
                payload = event.get("payload") or {}
                if payload.get("solved") is True:
                    flag_value = str(payload.get("flag") or "")
                    break

    key_pages: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    # flag-bearing interaction first (the money shot), then the first page.
    ordered = list(interactions)
    if flag_value:
        flagged = [i for i in interactions
                   if flag_value in i["output_head"] or _FLAG_RE.search(
                       i["output_head"])]
        ordered = flagged + [i for i in ordered if i not in flagged]
    for item in ordered:
        if not item["is_http"] or not item["url"]:
            continue
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        is_post = item.get("method") == "POST"
        key_pages.append({
            "url": item["url"],
            "seq": item["seq"],
            "worker": item.get("worker"),
            "method": item.get("method") or "GET",
            # Batch 5E (audit §4.4): a POST/session-state page cannot be
            # honestly reproduced by a bare GET replay — mark it as such
            # instead of pretending the screenshot is the original success.
            "replay": not is_post,
            "replay_note": ("POST/session-dependent — GET replay is a "
                            "best-effort view, NOT the original success "
                            "request" if is_post else ""),
            "reason": ("flag in response" if flag_value and (
                flag_value in item["output_head"]) else "http page"),
        })
        if len(key_pages) >= 4:
            break

    artifacts: dict[str, str] = {}
    arts = workspace / "arts"
    if arts.is_dir():
        for p in sorted(arts.glob("*")):
            if p.is_file():
                digest = hashlib.sha256()
                with p.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        digest.update(chunk)
                artifacts[p.name] = digest.hexdigest()

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "flag": flag_value or None,
        "http_interactions": interactions[-20:],
        "key_pages": key_pages,
        "screenshots": [],
        "artifacts": artifacts,
        "notes": [],
    }


def append_evidence_section(writeup_md: str, manifest: dict[str, Any],
                            *, shots_dir_name: str = "writeup-shots") -> str:
    """Deterministically append the evidence chapter to a writeup body.

    The writeup prompt forbids the model from running tools, so screenshots
    and artifact pointers are appended HOST-SIDE — the model cannot invent or
    omit them.
    """
    shots = manifest.get("screenshots") or []
    artifacts = manifest.get("artifacts") or {}
    lines = ["", "## 关键截图与证据", ""]
    if shots:
        lines.append("| # | 页面 | 采集方式 |")
        lines.append("|---|---|---|")
        for i, s in enumerate(shots, 1):
            lines.append(
                f"| {i} | {s.get('url') or s.get('name','')} "
                f"| {s.get('method', 'browser replay')} |")
        lines.append("")
        for i, s in enumerate(shots, 1):
            name = s.get("file") or ""
            if name:
                lines.append(f"![screenshot {i}]({shots_dir_name}/{name})")
        lines.append("")
    else:
        lines.append("- 本次未采集到截图（实例过期 / 目标不可达 / 非 web 题）。")
        for note in manifest.get("notes") or []:
            lines.append(f"- 采集说明: {note}")
        lines.append("")
    if artifacts:
        lines.append("原始输出产物（workspace/arts/，SHA-256 见 "
                     "writeup-evidence.json）：")
        for name in sorted(artifacts)[:10]:
            lines.append(f"- `arts/{name}`")
        lines.append("")
    return writeup_md.rstrip() + "\n" + "\n".join(lines)


__all__ = ["build_evidence_manifest", "append_evidence_section"]
