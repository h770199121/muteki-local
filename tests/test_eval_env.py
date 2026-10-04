"""D10 —— 评测环境冻结（eval_env.freeze_eval_env）的结构契约。

每次评测记录必须绑定：源码 commit、worker 镜像、模型身份（planner+启用
seat）、技能指纹、预算。任何探针失败必须显式标注 unavailable + 原因，
不得伪造，也不得让评测崩溃。纯标准库，宿主可直接导入。

Run:  python -X utf8 -B -m unittest tests.test_eval_env -v
"""

from __future__ import annotations

import unittest

from eval_env import freeze_eval_env


class FreezeShapeTests(unittest.TestCase):
    def test_returns_all_blocks(self):
        binding = freeze_eval_env(budget_s=1200, attempt=1)
        for key in ("captured_at", "git", "worker_image", "models",
                    "skills", "budget_s", "attempt"):
            self.assertIn(key, binding)
        self.assertEqual(binding["budget_s"], 1200)
        self.assertEqual(binding["attempt"], 1)

    def test_git_block_has_commit(self):
        block = freeze_eval_env()["git"]
        # 项目已是 Git 仓库（D11），commit 必须可得
        self.assertEqual(block["status"], "ok")
        self.assertEqual(len(block["commit"]), 40)
        self.assertIsInstance(block["dirty"], bool)

    def test_models_block_lists_enabled_seats(self):
        block = freeze_eval_env()["models"]
        self.assertEqual(block["status"], "ok")
        self.assertTrue(block["planner"]["base_url"], "planner 端点必须可读")
        self.assertIsInstance(block["enabled_seats"], list)
        for seat in block["enabled_seats"]:
            self.assertIn("model", seat)

    def test_skills_block_fingerprints_files(self):
        block = freeze_eval_env()["skills"]
        self.assertEqual(block["status"], "ok")
        self.assertIn("SKILL.md", block["files_sha256"])
        self.assertEqual(len(block["files_sha256"]["SKILL.md"]), 64)

    def test_worker_image_block_is_explicit(self):
        # 服务关闭/未设置时必须显式 unavailable+原因，而不是静默缺失
        block = freeze_eval_env()["worker_image"]
        self.assertIn(block["status"], ("ok", "unavailable"))
        if block["status"] == "unavailable":
            self.assertIn("reason", block)


if __name__ == "__main__":
    unittest.main()
