#!/usr/bin/env python3
"""Small CTF execution helpers: tool discovery, durable HTTP sessions, decoding.

Only stdlib dependencies. Commands return JSON and retain raw evidence on disk.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import difflib
import hashlib
from html.parser import HTMLParser
import http.cookiejar
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ENTRYPOINTS = {
    "bash": ["bash"], "curl": ["curl"], "jq": ["jq"], "rg": ["rg"],
    "gcc": ["gcc"], "gdb": ["gdb"], "tshark": ["tshark"],
    "tcpdump": ["tcpdump"], "binwalk": ["binwalk"], "exiftool": ["exiftool"],
    "foremost": ["foremost"], "sqlmap": ["sqlmap"], "ffuf": ["ffuf"],
    "gobuster": ["gobuster"], "nikto": ["nikto"], "nuclei": ["nuclei"],
    "radare2": ["r2", "radare2"], "ROPgadget": ["ROPgadget"],
    "sage": ["sage", "/opt/conda/bin/sage"],
    "ghidra-headless": ["analyzeHeadless", "/usr/share/ghidra/support/analyzeHeadless"],
    "volatility3": ["vol", "vol3"], "hashcat": ["hashcat"],
    "john": ["john", "/usr/sbin/john"], "zbarimg": ["zbarimg"],
    "zsteg": ["zsteg"], "7z": ["7z"], "unzip": ["unzip"],
}
PACKAGES = ["deepseek-harness-sdk", "pwntools", "angr", "z3-solver", "unicorn",
            "pycryptodome", "sympy", "gmpy2", "volatility3", "scapy", "Pillow"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def discover_tools():
    tools = {}
    for name, candidates in ENTRYPOINTS.items():
        resolved = next((p for item in candidates if (p := shutil.which(item))), None)
        tools[name] = {"status": "entry_found" if resolved else "missing", "path": resolved}
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": sys.version.split()[0], "executable": sys.executable,
            "uid": os.getuid() if hasattr(os, "getuid") else None,
            "tools": tools, "packages": packages,
            "note": "Entry/version discovery only. Use scripts/audit_worker_tools.py for real operations."}


class RedirectHistory(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.history = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.history.append({"status": code, "url": req.full_url, "location": newurl})
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            for key in ("Authorization", "Proxy-authorization", "Cookie"):
                redirected.remove_header(key)
        return redirected


class PageData(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.fields = [], {}

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name"):
            self.fields.setdefault(attrs["name"], []).append(attrs.get("value", ""))


def http_request(args):
    if urllib.parse.urlsplit(args.url).scheme not in ("http", "https"):
        raise ValueError("URL must use http or https")
    session = Path(args.session).resolve()
    session.mkdir(parents=True, exist_ok=True)
    cookie_path = session / "cookies.txt"
    jar = http.cookiejar.MozillaCookieJar(str(cookie_path))
    if cookie_path.exists():
        jar.load(ignore_discard=True, ignore_expires=False)
    redirects = RedirectHistory()
    proxy = {"http": args.proxy, "https": args.proxy} if args.proxy else {}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxy),
                                        urllib.request.HTTPCookieProcessor(jar), redirects)
    headers = {"User-Agent": "muteki-ctf-tools/1", "Accept-Encoding": "identity"}
    for header in args.header:
        key, sep, value = header.partition(":")
        if not sep or not key.strip():
            raise ValueError("--header must use Name: value")
        headers[key.strip()] = value.strip()
    form = []
    for value in args.form:
        key, sep, val = value.partition("=")
        if not sep:
            raise ValueError("--form must use name=value")
        form.append((key, val))
    data = None
    if form:
        data = urllib.parse.urlencode(form).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif args.data_file:
        data = Path(args.data_file).read_bytes()
    request = urllib.request.Request(args.url, data=data, headers=headers,
                                     method=args.method or ("POST" if data is not None else "GET"))
    started = time.monotonic()
    try:
        response = opener.open(request, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        # 4xx/5xx are useful target observations, not transport failures.
        response = exc
    with response:
        body = response.read(args.max_bytes + 1)
        truncated = len(body) > args.max_bytes
        body = body[:args.max_bytes]
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            text = body.decode(charset, errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        stamp = uuid.uuid4().hex
        body_path, meta_path = session / f"{stamp}.body", session / f"{stamp}.json"
        body_path.write_bytes(body)
        jar.save(ignore_discard=True, ignore_expires=False)
        try:
            cookie_path.chmod(0o600)
        except OSError:
            pass
        record = {"method": request.method, "requested_url": args.url,
                  "final_url": response.geturl(), "status": response.code,
                  "redirects": redirects.history, "headers": list(response.headers.items()),
                  "body_file": str(body_path), "body_sha256": digest(body),
                  "body_bytes": len(body), "truncated": truncated,
                  "elapsed_s": round(time.monotonic() - started, 3), "charset": charset}
    parser = PageData()
    parser.feed(text)
    if args.echo_field:
        record["echo"] = {"field": args.echo_field,
                          "submitted": [v for k, v in form if k == args.echo_field],
                          "observed": parser.fields.get(args.echo_field, [])}
    if args.compare:
        previous = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        old_body = Path(previous["body_file"]).read_bytes()
        diff_path = session / f"{stamp}.diff"
        diff_path.write_text("".join(difflib.unified_diff(
            old_body.decode("utf-8", errors="replace").splitlines(keepends=True),
            text.splitlines(keepends=True), fromfile="previous", tofile="current")), encoding="utf-8")
        record["comparison"] = {"status_changed": previous["status"] != record["status"],
                                "body_changed": digest(old_body) != digest(body),
                                "byte_delta": len(body) - len(old_body), "diff_file": str(diff_path)}
    meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**{k: v for k, v in record.items() if k != "headers"},
            "metadata_file": str(meta_path), "cookie_jar": str(cookie_path),
            "cookies": sorted({c.name for c in jar}), "preview": text[:args.preview_chars]}


def file_kind(data):
    for magic, kind in ((b"\x7fELF", "elf"), (b"PK\x03\x04", "zip"),
                        (b"\x89PNG\r\n\x1a\n", "png"), (b"%PDF-", "pdf"),
                        (b"\x1f\x8b", "gzip"), (b"\xff\xd8\xff", "jpeg")):
        if data.startswith(magic):
            return kind
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "binary"
    return "utf8-text" if all(c.isprintable() or c in "\r\n\t" for c in text) else "binary"


def decode_file(args):
    source = Path(args.input).resolve()
    raw = source.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    fragments = [text.strip()]
    if re.search(r"<[A-Za-z!/][^>]*>", text):
        parser = PageData()
        parser.feed(text)
        fragments = [fragment.strip() for fragment in parser.text if fragment.strip()]
    candidates, seen = [], set()
    formats = ("base64", "hex") if args.format == "auto" else (args.format,)
    output = Path(args.out_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        for fragment in fragments:
            compact = re.sub(r"\s+", "", fragment)
            pattern = r"[A-Za-z0-9+/_-]{16,}={0,2}" if fmt == "base64" else r"(?:[0-9a-fA-F]{2}){8,}"
            chunks = [compact, *re.findall(pattern, fragment)]
            for token in dict.fromkeys(chunks):
                try:
                    if fmt == "base64":
                        # Only terminal padding is accepted, including URL-safe unpadded data.
                        if not token or not re.fullmatch(r"[A-Za-z0-9+/_-]+={0,2}", token) or len(token) % 4 == 1:
                            continue
                        decoded = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
                    else:
                        decoded = bytes.fromhex(token.removeprefix("0x"))
                except (ValueError, binascii.Error):
                    continue
                if not decoded or digest(decoded) in seen:
                    continue
                seen.add(digest(decoded))
                kind = file_kind(decoded)
                path = output / f"{fmt}-{digest(decoded)[:16]}.bin"
                if path.exists() and path.read_bytes() != decoded:
                    raise ValueError(f"output collision: {path}")
                path.write_bytes(decoded)
                candidates.append({"format": fmt, "path": str(path), "bytes": len(decoded),
                                   "sha256": digest(decoded), "kind": kind,
                                   "preview": decoded.decode("utf-8", errors="replace")[:args.preview_chars]
                                   if kind == "utf8-text" else decoded[:32].hex()})
                if len(candidates) >= args.max_candidates:
                    break
            if len(candidates) >= args.max_candidates:
                break
        if len(candidates) >= args.max_candidates:
            break
    return {"input": str(source), "input_sha256": digest(raw), "candidates": candidates,
            "candidate_limit_reached": len(candidates) >= args.max_candidates,
            "note": "Decoded candidates are observations; validate the expected format and challenge semantics."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="discover real tool entrypoints and installed package versions")
    http_parser = sub.add_parser("http", help="request with persistent cookie jar and raw response evidence")
    http_parser.add_argument("url")
    http_parser.add_argument("--session", required=True, help="directory for cookie jar and request artifacts")
    http_parser.add_argument("--method")
    data = http_parser.add_mutually_exclusive_group()
    data.add_argument("--form", action="append", default=[], help="repeat name=value; URL encoding is automatic")
    data.add_argument("--data-file")
    http_parser.add_argument("--header", action="append", default=[])
    http_parser.add_argument("--proxy", help="explicit proxy; environment proxies are not used")
    http_parser.add_argument("--timeout", type=float, default=20)
    http_parser.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024)
    http_parser.add_argument("--preview-chars", type=int, default=2000)
    http_parser.add_argument("--echo-field", help="compare an input field's value with submitted form data")
    http_parser.add_argument("--compare", help="previous metadata JSON whose body should be compared")
    decoder = sub.add_parser("decode", help="extract base64/hex candidates including HTML-wrapped text")
    decoder.add_argument("input")
    decoder.add_argument("--out-dir", required=True)
    decoder.add_argument("--format", choices=("base64", "hex", "auto"), default="base64")
    decoder.add_argument("--max-candidates", type=int, default=32)
    decoder.add_argument("--preview-chars", type=int, default=2000)
    args = ap.parse_args()
    for field in ("timeout", "max_bytes", "max_candidates"):
        if hasattr(args, field) and getattr(args, field) <= 0:
            ap.error(f"{field} must be positive")
    if hasattr(args, "preview_chars") and args.preview_chars < 0:
        ap.error("preview_chars cannot be negative")
    try:
        result = discover_tools() if args.command == "doctor" else http_request(args) if args.command == "http" else decode_file(args)
    except (OSError, ValueError, http.cookiejar.LoadError, urllib.error.URLError) as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.command == "decode" and not result["candidates"] else 0


if __name__ == "__main__":
    sys.exit(main())
