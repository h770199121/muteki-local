"""Offline CLI tests with local HTTP fixtures; no external hosts or model API."""
from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills" / "kali-claw-kb" / "ctf_tools.py"


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        form = urllib.parse.parse_qs(body.decode())
        if self.path == "/login":
            self.send_response(302)
            self.send_header("Set-Cookie", "session=opaque; Path=/; HttpOnly")
            self.send_header("Location", "/home")
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            value = form.get("username", [""])[0].replace("admin", "")
            self.wfile.write(f'<input name="username" value="{value}">'.encode())

    def do_GET(self):
        authenticated = self.headers.get("Cookie") == "session=opaque"
        status = 200 if self.path != "/home" or authenticated else 403
        self.send_response(status)
        self.end_headers()
        self.wfile.write(b"SESSION_OK" if authenticated else b"ANONYMOUS")


class HelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "data", prefix="ctf-tools-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, "-X", "utf8", "-B", str(CLI), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertNotIn("Traceback", proc.stderr, proc.stderr)
        return proc.returncode, json.loads(proc.stdout)

    def test_cookie_and_redirect_survive_separate_processes(self):
        session = self.work / "session"
        rc, login = self.run_cli("http", self.url + "/login", "--session", session, "--form", "username=test")
        self.assertEqual(rc, 0)
        self.assertEqual(login["preview"], "SESSION_OK")
        self.assertEqual(login["redirects"][0]["status"], 302)
        rc, home = self.run_cli("http", self.url + "/home", "--session", session)
        self.assertEqual((rc, home["status"], home["preview"]), (0, 200, "SESSION_OK"))
        self.assertEqual(Path(home["body_file"]).read_bytes(), b"SESSION_OK")

    def test_http_error_is_preserved_as_a_target_observation(self):
        rc, response = self.run_cli("http", self.url + "/home", "--session", self.work)
        self.assertEqual((rc, response["status"]), (0, 403))
        self.assertTrue(Path(response["metadata_file"]).exists())

    def test_input_echo_and_response_diff_are_explicit(self):
        rc, before = self.run_cli("http", self.url + "/echo", "--session", self.work,
                                  "--form", "username=alice", "--echo-field", "username")
        rc, after = self.run_cli("http", self.url + "/echo", "--session", self.work,
                                 "--form", "username=admin", "--echo-field", "username",
                                 "--compare", before["metadata_file"])
        self.assertEqual(rc, 0)
        self.assertEqual(after["echo"], {"field": "username", "submitted": ["admin"], "observed": [""]})
        self.assertTrue(after["comparison"]["body_changed"])
        self.assertIn("alice", Path(after["comparison"]["diff_file"]).read_text())

    def test_truncation_is_declared(self):
        rc, response = self.run_cli("http", self.url, "--session", self.work, "--max-bytes", 3)
        self.assertEqual(rc, 0)
        self.assertTrue(response["truncated"])
        self.assertEqual(Path(response["body_file"]).read_bytes(), b"ANO")

    def test_invalid_url_returns_structured_failure(self):
        rc, result = self.run_cli("http", "file:///does-not-exist", "--session", self.work)
        self.assertEqual(rc, 2)
        self.assertIn("error", result)

    def test_html_wrapped_base64_preserves_decoded_bytes(self):
        expected = b"<?php /* TOOL_DECODE_OK */ ?>"
        source = self.work / "response.html"
        source.write_text('<meta charset="utf-8"><pre>' + base64.b64encode(expected).decode() + "</pre>", encoding="utf-8")
        rc, result = self.run_cli("decode", source, "--out-dir", self.work / "out")
        self.assertEqual(rc, 0)
        self.assertIn(expected, [Path(x["path"]).read_bytes() for x in result["candidates"]])

    def test_urlsafe_unpadded_binary_is_lossless(self):
        expected = b"\xfb\xff\x80binary\x00"
        source = self.work / "encoded.txt"
        source.write_text(base64.urlsafe_b64encode(expected).decode().rstrip("="), encoding="utf-8")
        rc, result = self.run_cli("decode", source, "--out-dir", self.work / "out")
        self.assertEqual(rc, 0)
        self.assertEqual(Path(result["candidates"][0]["path"]).read_bytes(), expected)

    def test_invalid_encoding_is_not_a_success(self):
        source = self.work / "bad.txt"
        source.write_text("***", encoding="utf-8")
        rc, result = self.run_cli("decode", source, "--out-dir", self.work / "out")
        self.assertEqual((rc, result["candidates"]), (1, []))


if __name__ == "__main__":
    unittest.main()
