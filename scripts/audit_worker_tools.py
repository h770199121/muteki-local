#!/usr/bin/env python3
"""Offline Worker tool audit using generated fixtures, never external targets.

Run inside the exact Worker image as its normal user. --deep adds Ghidra/angr/Sage.
The JSON distinguishes executable discovery, startup, and real fixture operations.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def run_probe(name, argv, cwd, scope="fixture", expected=None, timeout=30):
    started = time.monotonic()
    if not argv[0]:
        return {"name": name, "status": "MISSING", "scope": scope, "argv": argv}
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                errors="replace", timeout=timeout,
                                env={**os.environ, "TERM": "xterm", "PYTHONDONTWRITEBYTECODE": "1"})
        ok = result.returncode == 0 and (expected is None or expected in result.stdout)
        return {"name": name, "status": "PASS" if ok else "FAIL", "scope": scope,
                "argv": argv, "returncode": result.returncode,
                "elapsed_s": round(time.monotonic() - started, 3),
                "stdout": result.stdout, "stderr": result.stderr,
                "expected_stdout": expected}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "status": "FAIL", "scope": scope, "argv": argv,
                "elapsed_s": round(time.monotonic() - started, 3), "error": str(exc)}


class FixtureHTTP(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"MUTEKI_HTTP_TOOL_OK")


def audit(deep=False):
    spec = importlib.util.spec_from_file_location("ctf_tools", ROOT / "skills/kali-claw-kb/ctf_tools.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    discovery = module.discover_tools()
    paths = {key: value["path"] for key, value in discovery["tools"].items()}
    rows = []
    with tempfile.TemporaryDirectory(prefix="muteki-tools-") as temp:
        work = Path(temp)
        source, binary = work / "fixture.c", work / "fixture"
        source.write_text('#include <stdio.h>\nint main(void) { puts("MUTEKI_ELF_TOOL_OK"); return 0; }\n', encoding="utf-8")
        rows.append(run_probe("gcc.compile", [paths["gcc"], "-g", "-O0", str(source), "-o", str(binary)], work))
        http = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHTTP)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        jobs = [
            ("bash.execute", [paths["bash"], "-c", "printf MUTEKI_SHELL_TOOL_OK"], "fixture", "MUTEKI_SHELL_TOOL_OK"),
            ("curl.loopback", [paths["curl"], "--noproxy", "*", "-fsS", f"http://127.0.0.1:{http.server_port}"], "fixture", "MUTEKI_HTTP_TOOL_OK"),
            ("jq.parse", [paths["jq"], "-n", ".answer = 42"], "fixture", "42"),
            ("rg.search", [paths["rg"], "MUTEKI_ELF_TOOL_OK", str(source)], "fixture", "MUTEKI_ELF_TOOL_OK"),
        ]
        for name, flag in (("sqlmap", "--version"), ("ffuf", "-V"), ("gobuster", "--version"),
                           ("nikto", "-Version"), ("nuclei", "-version"), ("binwalk", "--help"),
                           ("foremost", "-V"), ("exiftool", "-ver"), ("volatility3", "--help"),
                           ("hashcat", "--version"), ("john", "--list=build-info"),
                           ("zbarimg", "--version"), ("zsteg", "--help")):
            jobs.append((name + ".startup", [paths[name], flag], "startup", None))
        py = sys.executable
        python_checks = {
            "z3.solve": "from z3 import *; x=Int('x'); s=Solver(); s.add(x+5==12); assert s.check()==sat; assert s.model()[x].as_long()==7; print('Z3_OK')",
            "crypto.roundtrip": "from Crypto.Cipher import AES; k=bytes(16); p=b'0123456789abcdef'; c=AES.new(k,AES.MODE_ECB).encrypt(p); assert AES.new(k,AES.MODE_ECB).decrypt(c)==p; print('CRYPTO_OK')",
            "sympy.factor": "import sympy; assert sympy.factorint(3233)=={53:1,61:1}; print('SYMPY_OK')",
            "gmpy2.root": "import gmpy2; assert gmpy2.iroot(343,3)==(7,True); print('GMPY_OK')",
            "unicorn.emulate": "from unicorn import *; from unicorn.x86_const import *; u=Uc(UC_ARCH_X86,UC_MODE_64); u.mem_map(0x1000,0x1000); u.mem_write(0x1000,bytes.fromhex('b82a000000')); u.emu_start(0x1000,0x1005); assert u.reg_read(UC_X86_REG_RAX)==42; print('UNICORN_OK')",
            "scapy.pcap": "from scapy.all import Ether,IP,UDP,Raw,wrpcap,rdpcap; p=Ether()/IP(dst='127.0.0.1')/UDP(sport=12345,dport=23456)/Raw(b'MUTEKI_PCAP_OK'); wrpcap('fixture.pcap',[p]); assert bytes(rdpcap('fixture.pcap')[0][Raw])==b'MUTEKI_PCAP_OK'; print('SCAPY_OK')",
            "pillow.image": "from PIL import Image; im=Image.new('RGB',(4,4),(255,0,0)); im.save('fixture.png'); assert Image.open('fixture.png').getpixel((0,0))==(255,0,0); print('PILLOW_OK')",
        }
        if binary.exists():
            python_checks["pwntools.elf-pattern"] = f"from pwn import ELF,cyclic,cyclic_find; e=ELF({str(binary)!r},checksec=False); assert e.bits==64; p=cyclic(100); assert cyclic_find(p[40:44])==40; print('PWNTOOLS_OK')"
            jobs.extend([
                ("gdb.execute", [paths["gdb"], "-q", "-batch", "-ex", "run", str(binary)], "fixture", "MUTEKI_ELF_TOOL_OK"),
                ("radare2.elf", [paths["radare2"], "-q", "-c", "iI", str(binary)], "fixture", "elf"),
                ("ROPgadget.elf", [paths["ROPgadget"], "--binary", str(binary), "--only", "ret"], "fixture", "Unique gadgets found"),
            ])
            if deep:
                python_checks["angr.elf-load"] = f"import angr; p=angr.Project({str(binary)!r},auto_load_libs=False); assert p.arch.bits==64; s=p.factory.entry_state(); assert s.addr==p.entry; print('ANGR_OK')"
        jobs.extend((name, [py, "-c", code], "fixture", "_OK") for name, code in python_checks.items())
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(run_probe, name, argv, work, scope, expected, 45)
                           for name, argv, scope, expected in jobs]
                rows.extend(f.result() for f in futures)
        finally:
            http.shutdown()
            http.server_close()
            thread.join(timeout=3)
        if (work / "fixture.pcap").exists():
            rows.append(run_probe("tshark.pcap", [paths["tshark"], "-r", str(work / "fixture.pcap"), "-T", "fields", "-e", "udp.dstport"], work, expected="23456"))
            rows.append(run_probe("tcpdump.pcap", [paths["tcpdump"], "-nr", str(work / "fixture.pcap"), "-A"], work, expected="MUTEKI_PCAP_OK"))
        else:
            rows.append({"name": "pcap.readers", "status": "SKIP", "reason": "scapy fixture unavailable"})
        if (work / "fixture.png").exists():
            rows.append(run_probe("exiftool.image", [paths["exiftool"], "-ImageWidth", str(work / "fixture.png")], work, expected="4"))
        if deep:
            rows.append(run_probe("sage.factor", [paths["sage"], "-c", "assert list(factor(3233)) == [(53,1),(61,1)]; print('SAGE_OK')"], work, expected="SAGE_OK", timeout=90))
            if binary.exists():
                rows.append(run_probe("ghidra.analyze", [paths["ghidra-headless"], str(work), "probe-project", "-import", str(binary), "-analysisTimeoutPerFile", "30", "-deleteProject"], work, expected="Analysis succeeded for file", timeout=100))
        else:
            rows.append({"name": "ghidra/angr/sage", "status": "SKIP", "reason": "use --deep for heavy probes"})
    summary = {status: sum(row["status"] == status for row in rows) for status in ("PASS", "FAIL", "MISSING", "SKIP")}
    return {"discovery": discovery, "summary": summary, "probes": rows,
            "limitations": ["Version/help probes do not establish exploitation capability.",
                            "No GPU cracking, real memory dump, live target, or LLM reasoning benchmark is performed."]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--output", help="save the complete audit including command output")
    args = ap.parse_args()
    report = audit(args.deep)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"summary": report["summary"], "output": str(output),
                          "issues": [p for p in report["probes"] if p["status"] != "PASS"]}, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["summary"]["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
