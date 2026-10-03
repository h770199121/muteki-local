"""Dump full KB-read commands from run-0005 and check worker cwd layout."""
import json
from pathlib import Path

S = Path(r"D:\AI\muteki-local\data\sessions")

events = []
for l in (S / "run-0005.jsonl").read_text(encoding="utf-8").splitlines():
    try:
        events.append(json.loads(l))
    except json.JSONDecodeError:
        continue

for e in events:
    if e["event_type"] != "tool.start":
        continue
    s = e["payload"].get("tool", "")
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
    if "kali-claw-kb" in s:
        print("SEQ", e.get("seq"), ":", s[:420])
        print("-" * 60)
