"""Host E2E unittest for the batched screenshot collector (batch 9, item 6C).

Serves two local pages — one with an `&`-carrying query string that used to be
mangled by the npx.cmd path — and asserts both PNGs land through the batched
node+chromium path. Skips cleanly when node/playwright are unavailable.
"""

from __future__ import annotations

import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "labs" / "nyu-ctf"))

from writeup_evidence import _node_batch_screenshot, _node_bin, _playwright_pkg_dir  # noqa: E402

PAGE_BODY = b"<html><body><h1>MUTEKI_SHOT_E2E</h1></body></html>"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(PAGE_BODY)


@unittest.skipUnless(_node_bin() and _playwright_pkg_dir(),
                     "node + playwright package not available on host")
class BatchScreenshotE2ETests(unittest.TestCase):
    def test_plain_and_ampersand_query_urls_both_capture(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = None
        try:
            thread = __import__("threading").Thread(
                target=httpd.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{httpd.server_port}"
            with tempfile.TemporaryDirectory(prefix="muteki-shot-e2e-") as td:
                out_dir = Path(td)
                jobs = [
                    {"name": "01-plain", "url": f"{base}/page1",
                     "out": str(out_dir / "01-plain.png"), "timeout_ms": 8000},
                    {"name": "02-amp", "url": f"{base}/page2?a=1&b=%20x",
                     "out": str(out_dir / "02-amp.png"), "timeout_ms": 8000},
                ]
                results = _node_batch_screenshot(jobs, total_timeout_s=90)
                self.assertEqual(results.get("01-plain"), "ok",
                                 f"plain page: {results}")
                self.assertEqual(results.get("02-amp"), "ok",
                                 f"&-query page: {results}")
                for job in jobs:
                    png = Path(job["out"])
                    self.assertTrue(png.is_file(), job["name"])
                    self.assertGreater(png.stat().st_size, 500, job["name"])
        finally:
            httpd.shutdown()
            httpd.server_close()
            if thread is not None:
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
