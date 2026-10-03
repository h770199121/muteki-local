"""Extract login/admin-related tool calls from failed no-pass-needed runs."""
import json
import re
from pathlib import Path

SESSIONS = Path(r"D:\AI\muteki-local\data\sessions")
CMD_RE = re.compile(r'"command":"((?:[^"\\]|\\.)*)"')

RUNS = [("run-0005", "A线 8888"), ("run-1374", "B线 18200"), ("run-1713", "C线 8890")]

for rid, tag in RUNS:
    events = []
    for l in (SESSIONS / f"{rid}.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    tools = []
    for e in events:
        if e["event_type"] == "tool.start":
            raw = e["payload"].get("tool", "")
            s = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
            tools.append(s)
    print(f"===== {tag} {rid}: {len(tools)} 次工具调用 =====")
    hits = 0
    for s in tools:
        if "login" not in s and "admin" not in s.lower():
            continue
        m = CMD_RE.search(s)
        cmd = m.group(1) if m else s[:200]
        try:
            cmd = cmd.encode().decode("unicode_escape")
        except Exception:
            pass
        if any(k in cmd for k in ("--data", "-d ", "username", "POST")):
            hits += 1
            if hits <= 14:
                print("  *", cmd[:180].replace("\n", " "))
    print(f"  （登录相关请求共 {hits} 条）")
    # 是否出现过双嵌套尝试
    nested = [s for s in tools if "adadminmin" in s or "admadmin" in s or "adminadmin" in s]
    print(f"  双嵌套 payload 尝试: {len(nested)} 次")
    # 是否发现过滤回显 oracle（session username 回显）
    echo = [s for s in tools if "value=" in s or "username\" value" in s or re.search(r"login.*grep", s)]
    print(f"  探测过滤回显: {len(echo)} 次")
