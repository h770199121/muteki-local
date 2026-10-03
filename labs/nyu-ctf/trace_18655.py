"""Where did run-18655 lose the flag? Trace: login -> /home fetch -> submit."""
import json
from pathlib import Path

events = []
for l in (Path(r"D:\AI\muteki-local\data\sessions\run-18655.jsonl")).read_text(encoding="utf-8").splitlines():
    try:
        events.append(json.loads(l))
    except json.JSONDecodeError:
        continue

print("=== submit-flag attempts (tool.start) ===")
n = 0
for e in events:
    if e["event_type"] != "tool.start":
        continue
    s = e["payload"].get("tool", "")
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
    if "submit-flag" in s:
        n += 1
        print(f"[{e.get('seq')}] {s[:260]}")
print("total submit attempts:", n)

print()
print("=== tool.results containing the flag text ===")
n2 = 0
for e in events:
    if e["event_type"] != "tool.result":
        continue
    s = json.dumps(e.get("payload", {}), ensure_ascii=False)
    if "wh0_n3ed5" in s:
        n2 += 1
        if n2 <= 3:
            print(f"[{e.get('seq')}]", s[:300])
print("results with flag:", n2)

print()
print("=== flag gate / candidate events ===")
for e in events:
    s = json.dumps(e.get("payload", {}), ensure_ascii=False)
    if e["event_type"] in ("flag.found", "flag_found", "flag.rejected", "flag.candidate") or "candidate" in s.lower() and "flag" in s:
        print(f"[{e['event_type']}][{e.get('seq')}]", s[:260])

print()
print("=== last 4 tool calls ===")
tools = [(e.get("seq"), e["payload"].get("tool", "")) for e in events if e["event_type"] == "tool.start"]
for seq, s in tools[-4:]:
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
    print(f"[{seq}]", s[:220])
