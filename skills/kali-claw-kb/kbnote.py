#!/usr/bin/env python3
"""Hindsight capture: turn an operator's post-run insight into a permanent KB note.

The human watches a run on the Command Deck, spots a breakthrough (a filter
behavior, a working payload shape, a tool quirk), and captures it with ONE
command:

  python3 kbnote.py add --domain web-sqli --tag nopass \
      "filter deletes 'admin' once; nest it: adadminmin'-- survives to admin'--"
  python3 kbnote.py add --symptom "login brute force useless" --tag gatekeeping \
      "403 on /admin bypassed via SCRIPT_NAME header (gunicorn)"
  python3 kbnote.py list [--tag nopass]

Notes land in kb/operator-insights.md (symlink-free, bind-mount friendly), get
indexed by kbsearch.py automatically (fingerprint rebuild), and reach every
future worker through the standard skill projection — no re-distill, no image
rebuild. Keep each note ONE fact + ONE working command/payload when possible.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

INSIGHTS = Path(__file__).resolve().parent / "kb" / "operator-insights.md"


def _load_notes() -> list[dict]:
    if not INSIGHTS.is_file():
        return []
    notes, cur = [], None
    for line in INSIGHTS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## N-(\d{8})-(\d+) \[([^\]]*)\] (\S+)$", line)
        if m:
            if cur:
                notes.append(cur)
            cur = {"id": f"N-{m.group(1)}-{m.group(2)}", "date": m.group(1),
                   "tags": [t for t in m.group(3).split(",") if t],
                   "domain": m.group(4), "body": []}
        elif cur is not None and line.strip():
            cur["body"].append(line)
    if cur:
        notes.append(cur)
    for n in notes:
        n["body"] = "\n".join(n["body"]).strip()
    return notes


def _next_id(notes: list[dict]) -> str:
    today = dt.datetime.now().strftime("%Y%m%d")
    seq = 1 + max([int(n["id"].split("-")[-1]) for n in notes
                   if n["id"].startswith(f"N-{today}-")] or [0])
    return f"N-{today}-{seq}"


def cmd_add(args) -> int:
    text = args.text.strip()
    if not text:
        print("empty insight text", file=sys.stderr)
        return 2
    notes = _load_notes()
    nid = _next_id(notes)
    tags = ",".join(t.strip() for t in (args.tag or "").split(",") if t.strip())
    domain = (args.domain or "general").strip()
    INSIGHTS.parent.mkdir(parents=True, exist_ok=True)
    header = ""
    if not INSIGHTS.is_file():
        header = (
            "# Operator insights (hindsight capture)\n\n"
            "Human-captured lessons from watching runs on the Command Deck. "
            "One note = one fact + one working command/payload. Indexed by "
            "kbsearch.py; projected into every worker automatically.\n\n---\n\n"
        )
    block = (
        f"\n## {nid} [{tags}] {domain}\n"
        f"_{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
        f"{text}\n\n---\n"
    )
    with open(INSIGHTS, "a", encoding="utf-8") as fh:
        if header:
            fh.write(header)
        fh.write(block)
    print(f"saved {nid} -> {INSIGHTS}")
    print("next worker picks it up automatically (skill projection); "
          "kbsearch rebuilds its index on next query.")
    return 0


def cmd_list(args) -> int:
    notes = _load_notes()
    if args.tag:
        notes = [n for n in notes if args.tag in n["tags"]]
    if not notes:
        print("no notes yet — capture one with: kbnote.py add \"insight\"")
        return 0
    for n in reversed(notes):
        print(f"{n['id']} [{','.join(n['tags'])}] {n['domain']}")
        print(f"  {n['body'][:180]}{'…' if len(n['body']) > 180 else ''}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture operator hindsight into the KB")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="capture one insight")
    p_add.add_argument("text", help="the insight (one fact + working command)")
    p_add.add_argument("--domain", default="general",
                       help="kb domain it belongs to (web-sqli, forensics, …)")
    p_add.add_argument("--tag", default="", help="comma-separated tags (challenge, symptom)")
    p_list = sub.add_parser("list", help="list captured notes")
    p_list.add_argument("--tag", default="")
    args = ap.parse_args()
    return cmd_add(args) if args.cmd == "add" else cmd_list(args)


if __name__ == "__main__":
    sys.exit(main())
