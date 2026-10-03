"""Real CLI regressions for the project-local KB (stdlib runner supported)."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "kali-claw-kb"


class KBSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "data", prefix="kb-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy2(SOURCE / "kbsearch.py", self.root)
        if (SOURCE / "search_terms.json").exists():
            shutil.copy2(SOURCE / "search_terms.json", self.root)
        (self.root / "kb").mkdir()
        (self.root / "kb" / "web-sqli.md").write_text(
            "# Web SQL injection\n\n## Login filter bypass\n"
            "Compare a login input with its filtered echo before choosing a bypass.\n",
            encoding="utf-8",
        )
        (self.root / "kb" / "web-xss.md").write_text(
            "# Cross-site scripting\n\n## Cookie stealing\n"
            "Session cookies can be stolen.\n", encoding="utf-8",
        )

    def run_search(self, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(self.root / "kbsearch.py"), *args],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )

    def test_chinese_symptom_reaches_the_english_technique(self):
        result = self.run_search("登录 过滤 绕过")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("web-sqli.md", result.stdout)

    def test_json_returns_real_source_lines_and_domain(self):
        result = self.run_search("login filter", "--domain", "web-sqli", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        hit = payload["hits"][0]
        self.assertEqual(hit["file"], "web-sqli.md")
        self.assertEqual(hit["line"], 3)
        self.assertIn("Login filter bypass", hit["title"])

    def test_mixed_query_keeps_chinese_meaning(self):
        result = self.run_search("login 过滤 绕过", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hits"][0]["file"], "web-sqli.md")

    def test_domain_is_a_filter_not_a_ranking_suggestion(self):
        result = self.run_search("cookie", "--domain", "web-sqli", "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hits"], [])

    def test_fts_operator_input_does_not_change_query_grammar(self):
        result = self.run_search('login OR " * : NEAR(', "--json")
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(result.returncode, (0, 1))
        json.loads(result.stdout)

    def test_fallback_discloses_relaxed_query(self):
        result = self.run_search("login nonexistentword", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["strategy"], "any_term")

    def test_unknown_chinese_is_not_silently_discarded(self):
        result = self.run_search("不存在的术语", "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("不存在的术语", json.loads(result.stdout)["terms"])

    def test_read_only_index_location_falls_back_to_memory(self):
        # A directory at the index filename cannot be opened as a SQLite file.
        (self.root / ".kbsearch-index.db").mkdir()
        result = self.run_search("login", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["index"], "memory")


if __name__ == "__main__":
    unittest.main()
