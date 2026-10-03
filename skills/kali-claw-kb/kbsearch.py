#!/usr/bin/env python3
"""Search the local CTF KB with bilingual terms and source-line evidence.

Examples: kbsearch.py "登录 过滤 绕过" --domain web-sqli --json
Persistent FTS5 is optional: read-only skill directories use an in-memory index.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
KB_DIR = ROOT / "kb"
INDEX = ROOT / ".kbsearch-index.db"
TERMS = ROOT / "search_terms.json"
SCHEMA_VERSION = "2"


def iter_chunks():
    """Keep heading ancestry and ignore headings inside fenced code blocks."""
    for md in sorted(KB_DIR.glob("*.md")):
        title, start, buf, headings, fence = md.stem, 1, [], {}, None
        for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            marker = re.match(r"^\s*(`{3,}|~{3,})", line)
            if marker:
                token = marker.group(1)
                if fence is None:
                    fence = (token[0], len(token))
                elif token[0] == fence[0] and len(token) >= fence[1]:
                    fence = None
                buf.append(line)
                continue
            heading = re.match(r"^(#{1,4})\s+(.+)$", line) if fence is None else None
            if heading:
                if buf:
                    yield md.name, title, start, "\n".join(buf)
                depth = len(heading.group(1))
                headings = {k: v for k, v in headings.items() if k < depth}
                headings[depth] = heading.group(2).strip()
                title = " / ".join(headings.values())
                start, buf = n, [line]
            else:
                buf.append(line)
        if buf:
            yield md.name, title, start, "\n".join(buf)


def source_fingerprint():
    h = hashlib.sha256(SCHEMA_VERSION.encode())
    for md in sorted(KB_DIR.glob("*.md")):
        h.update(md.name.encode("utf-8"))
        h.update(md.read_bytes())
    return h.hexdigest()


def build_index(con, fingerprint):
    con.execute("BEGIN IMMEDIATE")
    try:
        con.execute("DROP TABLE IF EXISTS chunks")
        con.execute("DROP TABLE IF EXISTS meta")
        con.execute("CREATE VIRTUAL TABLE chunks USING fts5(file, title, text, line UNINDEXED, tokenize='unicode61')")
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        con.executemany("INSERT INTO chunks VALUES (?,?,?,?)",
                        [(f, t, text, line) for f, t, line, text in iter_chunks()])
        con.execute("INSERT INTO meta VALUES ('fingerprint', ?)", (fingerprint,))
        con.commit()
    except Exception:
        con.rollback()
        raise


def open_index():
    fingerprint = source_fingerprint()
    con = None
    try:
        con = sqlite3.connect(str(INDEX), timeout=2)
        try:
            row = con.execute("SELECT v FROM meta WHERE k='fingerprint'").fetchone()
        except sqlite3.OperationalError:
            row = None
        if not row or row[0] != fingerprint:
            build_index(con, fingerprint)
        return con, "disk"
    except sqlite3.Error:
        if con is not None:
            con.close()
        con = sqlite3.connect(":memory:")
        try:
            build_index(con, fingerprint)
        except Exception:
            con.close()
            raise
        return con, "memory"


def query_groups(query):
    aliases = json.loads(TERMS.read_text(encoding="utf-8"))["aliases"] if TERMS.exists() else {}
    remaining, groups = query.casefold(), []
    for key in sorted(aliases, key=len, reverse=True):
        pattern = re.escape(key) if re.search(r"[\u3400-\u9fff]", key) else r"\b" + re.escape(key) + r"\b"
        if re.search(pattern, remaining):
            groups.append(aliases[key])
            remaining = re.sub(pattern, " ", remaining)
    groups.extend([[word] for word in re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]+", remaining)])
    return list(dict.fromkeys(tuple(g) for g in groups))


def search(con, groups, limit, domain=None):
    # Quote all user text so FTS operators cannot become query syntax.
    quoted = ["(" + " OR ".join('"' + term.replace('"', '""') + '"' for term in group) + ")"
              for group in groups]
    domain_clause = " AND (file = ? OR file = ?)" if domain else ""
    params = [f"{domain}.md", f"{domain}-payloads.md"] if domain else []
    for strategy, joiner in (("all_terms", " AND "), ("any_term", " OR ")):
        rows = con.execute(
            "SELECT file, title, line, text, bm25(chunks, 3.0, 8.0, 1.0, 0.0) AS rank "
            "FROM chunks WHERE chunks MATCH ?" + domain_clause + " ORDER BY rank, file, line LIMIT ?",
            [joiner.join(quoted), *params, limit],
        ).fetchall()
        if rows:
            return [{"file": f, "title": title, "line": int(line),
                     "path": f"kb/{f}", "excerpt": re.sub(r"\s+", " ", text).strip()[:400]}
                    for f, title, line, text, _ in rows], strategy
    return [], "no_match"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--domain", help="exact domain, e.g. web-sqli, tool-workflows")
    ap.add_argument("--json", action="store_true", help="machine-readable hits and retrieval strategy")
    args = ap.parse_args()
    if not 1 <= args.limit <= 50:
        ap.error("--limit must be between 1 and 50")
    if args.domain and not re.fullmatch(r"[a-z0-9-]+", args.domain):
        ap.error("--domain must be a domain basename")
    if not KB_DIR.is_dir():
        ap.error("kb/ directory not found next to kbsearch.py")
    try:
        groups = query_groups(args.query)
        if not groups:
            ap.error("query contains no searchable words")
        con, index = open_index()
        try:
            hits, strategy = search(con, groups, args.limit, args.domain)
        finally:
            con.close()
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"KB search failed: {exc}", file=sys.stderr)
        return 2
    payload = {"query": args.query, "terms": [t for group in groups for t in group],
               "domain": args.domain, "strategy": strategy, "index": index, "hits": hits}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"query: {args.query!r} — {len(hits)} hit(s); strategy={strategy}; index={index}")
        if strategy == "any_term":
            print("No exact combination matched; these are broader candidates. Check prerequisites.")
        for hit in hits:
            print(f"\n### {hit['path']}:{hit['line']} :: {hit['title']}\n    {hit['excerpt']}")
        print("\nRead the cited section before acting. For tools/session/decode: python3 .agents/skills/kali-claw-kb/ctf_tools.py --help")
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
