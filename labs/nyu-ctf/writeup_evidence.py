"""Host-side writeup evidence collector: manifest + browser screenshots.

Runs on the HOST (the web container has no browser) while the challenge
instance is still alive:

  1. build the evidence manifest from the run's event stream
     (muteki.solver.writeup_evidence.build_evidence_manifest);
  2. pick the key pages (flag-bearing response first, then first pages);
  3. replay each GET through Playwright (host chromium) and screenshot it
     into ``workspace/writeup-shots/``;
  4. write ``workspace/writeup-evidence.json`` and leave the screenshots for
     drivers.py to append to writeup.md.

Constraints / honesty:
  * GET replay only — POST / session-state pages are marked ``replay: false``
    with the reason instead of being silently faked;
  * collection timeouts NEVER block the run teardown (bounded, best-effort);
  * failure reasons are preserved per page in the manifest notes.

Usage:
  python -X utf8 -B labs/nyu-ctf/writeup_evidence.py \
      --run run-22883 [--sessions data/sessions] [--base http://host/] \
      [--shots 4] [--timeout 25]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# NOTE: insert the REPO ROOT (which contains the `muteki` package), not the
# package dir itself — `from muteki.solver...` needs the parent on sys.path.
sys.path.insert(0, str(ROOT))

from muteki.solver.writeup_evidence import build_evidence_manifest  # noqa: E402


def _load_events(sessions: Path, run_id: str) -> list[dict]:
    path = sessions / f"{run_id}.jsonl"
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _gate_flag(events: list[dict]) -> str | None:
    for e in events:
        if (e.get("event_type") or "") == "run.finished":
            payload = e.get("payload") or {}
            if payload.get("solved") is True and payload.get("flag"):
                return str(payload["flag"])
    return None


def _node_bin() -> str:
    import shutil
    return shutil.which("node") or ""


def _playwright_pkg_dir() -> str:
    """Locate the Node playwright package dir without touching a shell.

    Resolution order: MUTEKI_PLAYWRIGHT_PKG override → node's global
    node_modules (Windows npm -g convention: <node_dir>/node_modules) →
    npx cache. The old per-page path invoked `npx playwright`, whose .cmd
    shim routes argv through cmd.exe and mangles URLs containing & % ^ —
    the root cause of the "查询串失败" screenshots.
    """
    import os
    import shutil
    env = os.environ.get("MUTEKI_PLAYWRIGHT_PKG")
    if env and (Path(env) / "package.json").is_file():
        return env
    node = shutil.which("node")
    if node:
        candidate = Path(node).parent / "node_modules" / "playwright"
        if (candidate / "package.json").is_file():
            return str(candidate)
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        cache = Path(local_app) / "npm-cache" / "_npx"
        if cache.is_dir():
            for entry in sorted(cache.glob("*/node_modules/playwright")):
                if (entry / "package.json").is_file():
                    return str(entry)
    return ""


def _node_batch_screenshot(jobs: list[dict], total_timeout_s: int) -> dict:
    """Screenshot N pages in ONE persistent chromium process.

    Returns {name: detail} with detail == "ok" on success. URLs travel inside
    a JSON file (never the command line), so shell metacharacters in query
    strings cannot be mangled; a single browser launch removes the
    back-to-back cold-start race that made consecutive npx shots flaky.
    """
    import json as _json
    import subprocess
    import tempfile
    node = _node_bin()
    pkg = _playwright_pkg_dir()
    if not node or not pkg or not jobs:
        return {}
    script = HERE / "batch_screenshot.cjs"
    if not script.is_file():
        return {}
    results: dict = {}
    try:
        with tempfile.TemporaryDirectory(prefix="muteki-shots-") as temp:
            jobs_path = Path(temp) / "jobs.json"
            results_path = Path(temp) / "results.jsonl"
            jobs_path.write_text(_json.dumps(jobs), encoding="utf-8")
            subprocess.run(
                [node, str(script), pkg, str(jobs_path), str(results_path)],
                capture_output=True, text=True, timeout=total_timeout_s,
                cwd=str(HERE))
            if results_path.is_file():
                for line in results_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    name = row.get("name")
                    if name:
                        results[name] = ("ok" if row.get("ok")
                                         else str(row.get("detail") or "failed"))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"<batch>": f"{type(exc).__name__}: {exc}"[:200]}
    return results


def _screenshot(url: str, out_png: Path, timeout_s: int) -> tuple[bool, str]:
    """Replay one GET through a headless browser. Returns (ok, detail).

    Per-page FALLBACK for pages the batched collector (_node_batch_screenshot)
    could not capture. Two known hazards live here: npx.cmd routes argv through
    cmd.exe (URL query strings containing & % ^ get split/expanded), and every
    call cold-launches a browser (back-to-back profile race). Both are why the
    batched path is primary; this path keeps one spaced retry as mitigation.
    """
    import shutil
    import subprocess
    # Windows: npx is npx.cmd — resolve the full path or CreateProcess fails
    # with WinError 2.
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        # The playwright CLI ships a screenshot subcommand — no `require` needed
        # (the npx-cached package is not requirable from plain `node -e`).
        out_png.parent.mkdir(parents=True, exist_ok=True)
        # Back-to-back npx launches intermittently fail (browser/profile race,
        # observed as alternating successes) — one spaced retry settles it.
        last_detail = ""
        for attempt in range(2):
            if attempt:
                time.sleep(3)
            try:
                proc = subprocess.run(
                    [npx, "playwright", "screenshot",
                     "--viewport-size=1280,800", "--wait-for-timeout=1500",
                     url, str(out_png)],
                    capture_output=True, text=True,
                    timeout=timeout_s + 40, cwd=str(HERE))
                if proc.returncode == 0 and out_png.is_file():
                    return True, "ok"
                last_detail = (proc.stderr or proc.stdout
                               or "npx playwright failed")[:500]
            except subprocess.TimeoutExpired:
                last_detail = f"browser timeout after {timeout_s + 40}s"
        return False, last_detail
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright not installed on host (neither npx nor python)"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(url, timeout=timeout_s * 1000,
                          wait_until="domcontentloaded")
                page.wait_for_timeout(1200)
                out_png.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(out_png), full_page=False)
                return True, "ok"
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 — collector must never raise
        return False, f"{type(exc).__name__}: {exc}"[:200]


def collect(*, run_id: str, sessions: Path, shots: int = 4,
            timeout_s: int = 25, browser: bool = True) -> dict:
    workspace = sessions / run_id / "workspace"
    events = _load_events(sessions, run_id)
    manifest = build_evidence_manifest(events, workspace=workspace,
                                       flag=_gate_flag(events))
    notes: list[str] = manifest["notes"]

    if not browser:
        manifest["notes"].append("browser replay disabled (--no-browser)")
    else:
        # Batch 5E: only GET-replayable pages get screenshots — POST/session
        # pages are recorded with their reason instead of a misleading image.
        pages = [p for p in manifest["key_pages"][:shots * 2]
                 if p.get("replay", True)][:shots]
        skipped_post = [p for p in manifest["key_pages"]
                        if not p.get("replay", True)]
        for p in skipped_post:
            notes.append(
                f"POST/会话态页面不截图重放: {p.get('url')} "
                f"(seq={p.get('seq')}) — 原始成功请求不可由 GET 还原")
        shots_dir = workspace / "writeup-shots"
        # Batch 5E (audit §4.4): persist the manifest after EVERY screenshot —
        # a total-timeout kill must not lose already-collected evidence.
        out_path = workspace / "writeup-evidence.json"

        def _save() -> None:
            out_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8")

        _save()
        shots_dir.mkdir(parents=True, exist_ok=True)
        # Batch 9 (6C): one persistent node+chromium process for ALL shots.
        # URLs travel via a JSON file — cmd.exe can no longer mangle query
        # strings (& % ^), and no per-shot cold launch means no profile race.
        # Per-page results land incrementally; a killed batch still yields the
        # partial JSONL, and any page without "ok" falls back to the legacy
        # per-page path once before being recorded as failed.
        jobs = [
            {"name": f"{i:02d}-seq{page['seq']}", "url": page["url"],
             "out": str(shots_dir / f"{i:02d}-seq{page['seq']}.png"),
             "timeout_ms": timeout_s * 1000}
            for i, page in enumerate(pages, 1)
        ]
        batch = _node_batch_screenshot(
            jobs, total_timeout_s=timeout_s * max(1, len(jobs)) + 90)
        for job, page in zip(jobs, pages):
            name = Path(job["out"]).name
            detail = batch.get(job["name"])
            ok = detail == "ok" and Path(job["out"]).is_file()
            if not ok:
                ok2, detail2 = _screenshot(job["url"], Path(job["out"]),
                                           timeout_s)
                if ok2:
                    ok, detail = True, "ok"
                else:
                    detail = (f"{detail or 'batch missing'}; "
                              f"per-page fallback: {detail2}")
            if ok:
                manifest["screenshots"].append({
                    "file": name, "url": page["url"], "seq": page["seq"],
                    "method": "GET replay (host playwright, batched)",
                    "replay": True,
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                })
            else:
                # Never fake it: a failed replay is recorded with its reason.
                manifest["notes"].append(
                    f"截图失败 {page['url']}: {detail}")
                page["replay"] = False
                page["replay_error"] = detail
            _save()
        skipped = len(manifest["key_pages"]) - len(pages)
        if skipped > 0:
            notes.append(f"{skipped} key pages beyond the --shots limit were "
                         "not replayed")

    out_path = workspace / "writeup-evidence.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    manifest["_written_to"] = str(out_path)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--sessions",
                    default=str(HERE.parents[1] / "data" / "sessions"))
    ap.add_argument("--shots", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--no-browser", action="store_true",
                    help="manifest only (no screenshots)")
    args = ap.parse_args()
    manifest = collect(run_id=args.run,
                       sessions=Path(args.sessions),
                       shots=args.shots, timeout_s=args.timeout,
                       browser=not args.no_browser)
    print(json.dumps({
        "flag": manifest.get("flag"),
        "key_pages": len(manifest.get("key_pages") or []),
        "screenshots": len(manifest.get("screenshots") or []),
        "notes": manifest.get("notes"),
        "written_to": manifest.get("_written_to"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
