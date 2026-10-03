"""B-line no-pass-needed forensic: framework-provided vs model-used."""
import json
import re
from pathlib import Path

S = Path(r"D:\AI\muteki-local\data\sessions")

def load(rid):
    ev = []
    for l in (S / f"{rid}.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            ev.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    return ev

def tools_of(events):
    out = []
    for e in events:
        if e["event_type"] == "tool.start":
            s = e["payload"].get("tool", "")
            out.append(s if isinstance(s, str) else json.dumps(s, ensure_ascii=False))
    return out

print("=" * 70)
print("1) run-18652 (B线, prompt kb-hint) 派发的 intents（planner 给 worker 的方向）")
ev = load("run-18652")
intents = [e["payload"].get("goal", "") for e in ev if e["event_type"] == "blackboard.delta"
           and "intent" in json.dumps(e.get("payload", {}))[:60]]
bb = [json.dumps(e.get("payload", {}), ensure_ascii=False) for e in ev if e["event_type"] == "blackboard.delta"]
goals = set()
for b in bb:
    m = re.search(r'"goal":\s*"([^"]{5,120})', b)
    if m:
        goals.add(m.group(1))
for g in sorted(goals)[:8]:
    print("  intent:", g)

print()
print("=" * 70)
print("2) run-18653 (B线, AGENTS.md 挂点) worker 是否读过 AGENTS.md / 关键技术使用")
ev2 = load("run-18653")
t2 = tools_of(ev2)
checks = {
    "cat/sed AGENTS.md": lambda s: "AGENTS.md" in s,
    "读 KB 文件": lambda s: "kali-claw-kb" in s and (".md" in s),
    "skill 工具调用": lambda s: s.startswith("skill:"),
    "admin'-- 完整注释": lambda s: "admin%27--" in s or "admin'--" in s,
    "'-- 后缀（任意用户名）": lambda s: re.search(r"--(['\"%]|$)|%27%2D%2D|--$", s) is not None and "username" in s.lower(),
    "回显对比(value= 提取)": lambda s: "value=" in s,
    "adadminmin 嵌套": lambda s: "adadminmin" in s,
}
for name, fn in checks.items():
    print(f"  {name}: {sum(1 for s in t2 if fn(s))}")

print()
print("=" * 70)
print("3) dsh harness 是否把 AGENTS.md 注入 worker 上下文（机制核查）")
bridge = Path(r"D:\AI\muteki-local\muteki\solver\deepseek_harness_worker.py")
txt = bridge.read_text(encoding="utf-8", errors="replace")
for kw in ("AGENTS.md", "workspaceContext", "workspace", "cwd"):
    cnt = txt.count(kw)
    print(f"  bridge 中 '{kw}' 出现 {cnt} 次")
# harness 上下文注入: 看 bridge 是否传 workspace/cordis workspaceContext
i = txt.find("workspaceContext")
if i >= 0:
    print("  上下文片段:", txt[max(0, i-200):i+200].replace("\n", " ")[:350])

print()
print("=" * 70)
print("4) run-18653 全部 username= payload 序列（模型思路演化）")
seen = []
for s in t2:
    for m in re.finditer(r"username(?:=|%3[dD])((?:[^&\"' \\]|%27|%20){2,70})", s):
        v = m.group(1)
        if v not in seen:
            seen.append(v)
for v in seen[:25]:
    print("  ", v[:70])

print()
print("=" * 70)
print("5) 对照：人工解法 3 条命令（同框架同镜像已验证）")
print("   curl POST username=adadminmin'-- → 302 /home → GET /home 含 flag")
print("   B 线轨迹 vs 解法差: 未做回显对比(0) + 未做嵌套(0) + 未用 -- 注释(见上)")
