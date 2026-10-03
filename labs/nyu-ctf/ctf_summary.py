#!/usr/bin/env python3
"""Aggregate local CTF solve rates per model line from results.jsonl."""
import json
from collections import defaultdict

def line_of(tag: str) -> str:
    t = tag.upper()
    for key, name in (("A-", "A-line(8888 IQ3_S)"), ("B-", "B-line(18200 Bonsai)"),
                      ("C-", "C-line(8890 Occamy)"), ("BASE-SWIFT", "Swift(18202)")):
        if t.startswith(key):
            return name
    if "SWIFT" in t or "BASE" in t:
        return "Swift/base(18202)"
    return tag.split("-")[0]

agg = defaultdict(lambda: {"n": 0, "s": 0, "ch": defaultdict(lambda: [0, 0])})
with open(r"D:\AI\muteki-local\labs\nyu-ctf\results.jsonl", encoding="utf-8") as fh:
    for line in fh:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        tag = r.get("tag", "")
        ch = r.get("challenge", "?")
        # exclude invalid runs
        if r.get("tool_calls", 1) == 0 and r.get("events", 1) <= 3:
            continue
        ln = line_of(tag)
        a = agg[ln]
        a["n"] += 1
        a["s"] += 1 if r.get("solved") else 0
        a["ch"].setdefault(ch, [0, 0])
        a["ch"][ch][1] += 1
        a["ch"][ch][0] += 1 if r.get("solved") else 0

for ln, a in agg.items():
    chs = " ".join(f"{c}:{s}/{n}" for c, (s, n) in sorted(a["ch"].items()))
    print(f"{ln:24s} solved {a['s']}/{a['n']}   [{chs}]")
