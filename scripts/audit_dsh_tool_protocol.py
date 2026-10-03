#!/usr/bin/env python3
"""Exercise the real Muteki dsh bridge with a deterministic loopback model API.

This validates tool transport, not LLM reasoning or CTF success. Run in the
Worker image with --network none. No real credentials or external model are used.
"""
from __future__ import annotations

import argparse
import base64
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


def protocol_audit():
    requests_seen, commands = [], [
        "python3 .agents/skills/kali-claw-kb/ctf_tools.py doctor",
        'python3 .agents/skills/kali-claw-kb/kbsearch.py "登录 过滤 绕过" --domain web-sqli --json',
        "python3 .agents/skills/kali-claw-kb/ctf_tools.py decode fixture.html --out-dir decoded",
        "python3 -c \"from z3 import Int, Solver, sat; x=Int('x'); s=Solver(); s.add(x+5==12); assert s.check()==sat; assert s.model()[x].as_long()==7; print('MUTEKI_Z3_PROTOCOL_OK')\"",
        "gdb -q -batch -ex 'file /bin/true' -ex 'info files'",
    ]

    class ReplayHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            tool_schemas = [tool["function"] for tool in body.get("tools", []) if "function" in tool]
            bash = next((tool for tool in tool_schemas if tool["name"] == "bash"), None)
            index = len(requests_seen)
            requests_seen.append({"path": self.path, "model": body.get("model"),
                                  "stream": body.get("stream"),
                                  "tool_names": [tool["name"] for tool in tool_schemas],
                                  "received_tool_results": sum(m.get("role") == "tool" for m in body.get("messages", []))})
            tool_call = None
            if index < len(commands) and bash:
                tool_call = {"id": f"audit_call_{index}", "type": "function",
                             "function": {"name": bash["name"], "arguments": json.dumps({"command": commands[index], "description": "Offline deterministic transport fixture"})}}
            content = None if tool_call else "OFFLINE_PROTOCOL_OK"
            reason = "tool_calls" if tool_call else "stop"
            response_id = f"audit_completion_{index}"
            common = {"id": response_id, "created": int(time.time()), "model": body.get("model", "audit")}
            self.send_response(200)
            if body.get("stream"):
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                delta = {"role": "assistant", "content": content or ""}
                if tool_call:
                    delta["tool_calls"] = [{"index": 0, **tool_call}]
                for part in ({**common, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                             {**common, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": reason}]}):
                    self.wfile.write(("data: " + json.dumps(part) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                message = {"role": "assistant", "content": content}
                if tool_call:
                    message["tool_calls"] = [tool_call]
                self.wfile.write(json.dumps({**common, "object": "chat.completion", "choices": [{"index": 0, "message": message, "finish_reason": reason}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode())

    with tempfile.TemporaryDirectory(prefix="muteki-dsh-tool-probe-") as temp:
        work = Path(temp)
        stager_path = ROOT / "muteki/solver/worker_skills.py"
        spec = importlib.util.spec_from_file_location("worker_skills", stager_path)
        stager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stager)
        previous = os.environ.get("MUTEKI_EXTRA_SKILLS_DIR")
        try:
            os.environ["MUTEKI_EXTRA_SKILLS_DIR"] = str(ROOT / "skills")
            staged = stager.stage_extra_skills(work, engine="dsh", container=True)
        finally:
            if previous is None:
                os.environ.pop("MUTEKI_EXTRA_SKILLS_DIR", None)
            else:
                os.environ["MUTEKI_EXTRA_SKILLS_DIR"] = previous
        (work / "fixture.html").write_text('<meta charset="utf-8"><pre>' + base64.b64encode(b"MUTEKI_DECODE_PROTOCOL_OK").decode() + "</pre>", encoding="utf-8")
        server = ThreadingHTTPServer(("127.0.0.1", 0), ReplayHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = {**os.environ, "DEEPSEEK_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
               "DEEPSEEK_API_KEY": "offline-fixture-key", "DSH_CWD": str(work),
               "DSH_HOME": str(work / ".dsh-home"), "DSH_SESSION_ROOT": str(work / "sessions"),
               "DSH_TELEMETRY_DISABLED": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        bridge = ROOT / "muteki/solver/deepseek_harness_worker.py"
        try:
            result = subprocess.run([sys.executable, str(bridge), "--model", "offline-protocol-fixture",
                                     "--session", "session-offline-tool-audit", "--",
                                     "Run the offline local tool conformance fixture. Do not submit any Flag."],
                                    cwd=work, env=env, capture_output=True, text=True,
                                    errors="replace", timeout=90)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        events = []
        for line in result.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        calls = [e for e in events if e.get("type") == "tool"]
        outputs = [e for e in events if e.get("type") == "tool_result"]
        decoded = [p.read_bytes() for p in (work / "decoded").glob("*.bin")] if (work / "decoded").exists() else []
        checks = {
            "bridge_exit_zero": result.returncode == 0,
            "all_requested_tool_calls": len(calls) == len(commands),
            "matching_tool_results": len(outputs) == len(commands) and {e.get("call_id") for e in calls} == {e.get("call_id") for e in outputs},
            "tool_errors_absent": bool(outputs) and not any(e.get("is_error") for e in outputs),
            "real_doctor_output": any('"ghidra-headless"' in e.get("output", "") for e in outputs),
            "real_chinese_search_output": any('"file": "web-sqli.md"' in e.get("output", "") for e in outputs),
            "decoded_artifact_matches": b"MUTEKI_DECODE_PROTOCOL_OK" in decoded,
            "z3_solver_executed": any("MUTEKI_Z3_PROTOCOL_OK" in e.get("output", "") for e in outputs),
            "gdb_loaded_real_elf": any("elf64-x86-64" in e.get("output", "") for e in outputs),
            "final_result_observed": any(e.get("type") == "result" and e.get("text") == "OFFLINE_PROTOCOL_OK" for e in events),
        }
        return {"kind": "deterministic_model_protocol_fixture", "checks": checks,
                "passed": all(checks.values()), "staged": staged, "requests": requests_seen,
                "events": events, "stderr": result.stderr, "returncode": result.returncode,
                "limitations": "Real dsh SDK/tools/bridge; simulated model decisions. Not a real-model or Flag-gate/CTF benchmark."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    try:
        report = protocol_audit()
    except Exception as exc:
        report = {"passed": False, "error": type(exc).__name__, "detail": str(exc)}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("passed", "checks", "error", "detail", "returncode") if k in report}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
