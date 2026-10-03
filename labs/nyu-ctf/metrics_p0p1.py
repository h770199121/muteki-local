"""P0/P1 behavior metrics for the latest run."""
import json
import glob
import os
from collections import Counter

f = sorted(glob.glob(r"D:\AI\muteki-local\data\sessions\*.jsonl"), key=os.path.getmtime)[-1]
events = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
tools = [e["payload"].get("tool", "") for e in events if e["event_type"] == "tool.start"]
tools = [t if isinstance(t, str) else json.dumps(t, ensure_ascii=False) for t in tools]
blob = json.dumps(events, ensure_ascii=False)

print(os.path.basename(f), len(events), "events,", len(tools), "calls")
print(dict(Counter(e["event_type"] for e in events)))
print("KB/kbsearch 引用      :", sum(1 for s in tools if "kali-claw-kb" in s or "kbsearch" in s))
print("read-directives 执行  :", sum(1 for s in tools if "read-directives" in s))
print("FAILED_PROBE 输出行   :", blob.count("FAILED_PROBE="))
print("引号/注释注入         :", sum(1 for s in tools if "%27" in s or ("'--") in s))
print("无空格变体 /**/       :", sum(1 for s in tools if "/**/" in s))
print("嵌套 adadminmin       :", sum(1 for s in tools if "adadminmin" in s))
print("reflection 事件       :", sum(1 for e in events if e["event_type"] == "blackboard.delta" and "reflection" in json.dumps(e.get("payload", {}))))
tools_last = tools[-3:] if tools else []
for s in tools_last:
    print("recent:", s[:150])
