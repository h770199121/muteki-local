"""Batch 4-2 —— writeup 证据清单与确定性附加章节（muteki.solver.writeup_evidence）。

真实导入消费：build_evidence_manifest 从合成事件流提取 HTTP 交互/flag 页/artifact
指纹；append_evidence_section 验证截图章节确定性附加与无截图时的诚实说明。
纯标准库，宿主直接导入。

Run:  python -X utf8 -B -m unittest tests.test_writeup_evidence -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from muteki.solver.writeup_evidence import (  # noqa: E402
    append_evidence_section,
    build_evidence_manifest,
)

FLAG = "CTF2{11111111-2222-3333-4444-555555555555}"


def _ev(etype, seq, **payload):
    return {"event_type": etype, "seq": seq, "run_id": "r", "payload": payload}


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name) / "workspace"
        arts = self.workspace / "arts"
        arts.mkdir(parents=True, exist_ok=True)
        (arts / "a1b2c3d4e5f6.txt").write_text(
            f"login success page\n{FLAG}\n", encoding="utf-8")

    def test_manifest_extracts_flag_page_and_artifacts(self):
        events = [
            _ev("tool.start", 1, tool="bash: curl -s http://t.local/"),
            _ev("tool.result", 2, result={"condensed": "<html>login page</html>"}),
            _ev("tool.start", 3,
                tool="bash: curl -s 'http://t.local/check.php?username=admin%27--'"),
            _ev("tool.result", 4,
                result={"condensed": f"<html>hello admin {FLAG}</html>"}),
            _ev("run.finished", 9, solved=True, flag=FLAG),
        ]
        m = build_evidence_manifest(events, workspace=self.workspace)
        self.assertEqual(m["flag"], FLAG)
        self.assertTrue(m["http_interactions"])
        # flag 页排第一且标注原因；URL 来自配对命令
        self.assertEqual(m["key_pages"][0]["reason"], "flag in response")
        self.assertIn("check.php", m["key_pages"][0]["url"])
        # artifacts 指纹
        self.assertIn("a1b2c3d4e5f6.txt", m["artifacts"])
        self.assertEqual(len(m["artifacts"]["a1b2c3d4e5f6.txt"]), 64)

    def test_key_pages_urls_come_from_commands(self):
        events = [
            _ev("tool.start", 1,
                tool="bash: curl -s 'http://t.local/index.php?x=1'"),
            _ev("tool.result", 2, result={"condensed": "<html>hi</html>"}),
        ]
        m = build_evidence_manifest(events, workspace=self.workspace)
        self.assertEqual(m["key_pages"][0]["url"], "http://t.local/index.php?x=1")

    def test_append_section_with_screenshots(self):
        m = build_evidence_manifest([], workspace=self.workspace)
        m["screenshots"] = [
            {"file": "01-seq4.png", "url": "http://t.local/check.php",
             "method": "GET replay"},
        ]
        out = append_evidence_section("## Flag\n\nCTF2{x}\n", m)
        self.assertIn("## 关键截图与证据", out)
        self.assertIn("![screenshot 1](writeup-shots/01-seq4.png)", out)
        self.assertIn("`arts/a1b2c3d4e5f6.txt`", out)

    def test_append_section_without_shots_is_honest(self):
        m = build_evidence_manifest([], workspace=self.workspace)
        m["notes"] = ["截图失败 http://t.local/: timeout"]
        out = append_evidence_section("body", m)
        self.assertIn("本次未采集到截图", out)
        self.assertIn("timeout", out)


if __name__ == "__main__":
    unittest.main()
