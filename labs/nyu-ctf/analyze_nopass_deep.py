"""Deeper dive: SQLi attempts + filter-echo interpretation in the 3 failed runs."""
import json
import re
from pathlib import Path

SESSIONS = Path(r"D:\AI\muteki-local\data\sessions")
RUNS = [("run-0005", "A线"), ("run-1374", "B线"), ("run-1713", "C线")]

for rid, tag in RUNS:
    events = []
    for l in (SESSIONS / f"{rid}.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    tools = [e["payload"].get("tool", "") for e in events if e["event_type"] == "tool.start"]
    tools = [t if isinstance(t, str) else json.dumps(t, ensure_ascii=False) for t in tools]

    def count(*keys):
        return sum(1 for s in tools if any(k in s for k in keys))

    print(f"===== {tag} {rid} ({len(tools)} calls) =====")
    print("  含单引号(')的请求      :", count("username=admin%27", "username=admin'", "username=%27", "ad%27", "'--", "%27--"))
    print("  含 OR/UNION/SELECT 注入:", count("OR+1", "OR%1", "' OR", "%27+OR", "UNION", "union"))
    print("  提交过 flag 假设       :", count("submit-flag", "FOUND_FLAG"))
    print("  NoSQL/$regex 尝试      :", count("$regex", "$gt", "$ne", "ne JSON", "json)"))
    # A 线：登录页 value= 回显的解读
    if rid == "run-0005":
        results = [e["payload"].get("result", {}) for e in events if e["event_type"] == "tool.result"]
        echoed = [r for r in results if "value=" in str(r)]
        print("  -- 登录页 value= 回显样例 --")
        for r in echoed[:3]:
            text = str(r)
            m = re.search(r'value="([^"]{0,60})"', text)
            print("     echo ->", m.group(1) if m else "(无 value)")
    # 最后一条 reasoning 内容（worker 在想什么）
    reasoning = [e["payload"].get("text", "") for e in events if e["event_type"] == "reasoning.delta"]
    if reasoning:
        tail = "".join(reasoning)[-400:]
        print(f"  -- 末段 reasoning 节选: {tail[-300:]}")
    print()
