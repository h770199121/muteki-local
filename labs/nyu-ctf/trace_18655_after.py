"""Find the successful 302 /home moment and what the worker did after it."""
import json
from pathlib import Path

events = []
for l in (Path(r"D:\AI\muteki-local\data\sessions\run-18655.jsonl")).read_text(encoding="utf-8").splitlines():
    try:
        events.append(json.loads(l))
    except json.JSONDecodeError:
        continue

hits = []
for e in events:
    if e["event_type"] == "tool.result":
        s = json.dumps(e.get("payload", {}), ensure_ascii=False)
        if "Redirecting to /home" in s or ('"/home"' in s and "302" in s):
            hits.append(e.get("seq"))

print("302->/home result seqs:", hits)

if hits:
    first = hits[0]
    after = [e for e in events if isinstance(e.get("seq"), int) and e["seq"] > first]
    print(f"\n=== {len(after)} events after first success ===")
    shown = 0
    for e in after:
        if e["event_type"] == "tool.start":
            s = e["payload"].get("tool", "")
            s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
            shown += 1
            if shown <= 12:
                print(f"[{e.get('seq')}]", s[:200])
    print("total tool calls after success:", shown)
    # reasoning after success
    r = "".join(e["payload"].get("text", "") for e in after if e["event_type"] == "reasoning.delta")
    print("\nreasoning after success (last 400):", r[-400:])
