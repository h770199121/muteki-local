"""D06/audit 5.7 —— 技能投影必须可见：manifest、内容指纹、失败不再静默。

stage_extra_skills 此前对"源不可读/复制失败"一律静默跳过，事后无法区分
"当前技能"、"旧 Worker 副本"与"从未送达"。现在的契约：

  * 每次投影在 Worker cwd 落 ``skills-projection.json``；
  * 每个条目带 per-file SHA-256（copied / pre_existing 都有指纹）；
  * 复制失败记入 failures 并打 stderr 警告，但不阻断启动（extra skills 仍
    是 operator convenience）；
  * 源目录不可读 → manifest 记 source_unavailable。

纯标准库，宿主可直接导入。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from muteki.solver.worker_skills import stage_extra_skills  # noqa: E402


class ProjectionManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workdir = Path(self._tmp.name) / "workspace"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.src = Path(self._tmp.name) / "skills-src"
        (self.src / "kali-claw-kb" / "kb").mkdir(parents=True)
        (self.src / "kali-claw-kb" / "SKILL.md").write_text(
            "# kali claw kb\n", encoding="utf-8")
        (self.src / "kali-claw-kb" / "kb" / "web-sqli.md").write_text(
            "payload table\n", encoding="utf-8")
        self._old_env = os.environ.get("MUTEKI_EXTRA_SKILLS_DIR")
        os.environ["MUTEKI_EXTRA_SKILLS_DIR"] = str(self.src)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self._old_env is None:
            os.environ.pop("MUTEKI_EXTRA_SKILLS_DIR", None)
        else:
            os.environ["MUTEKI_EXTRA_SKILLS_DIR"] = self._old_env

    def _manifest(self) -> dict:
        path = self.workdir / "skills-projection.json"
        self.assertTrue(path.is_file(), "投影后必须落 manifest")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_copy_records_status_and_fingerprints(self):
        staged = stage_extra_skills(self.workdir, engine="dsh")
        self.assertTrue(staged, "正常投影应返回目标路径")
        m = self._manifest()
        self.assertEqual(m["status"], "ok")
        self.assertEqual(m["source_dir"], str(self.src))
        self.assertEqual(len(m["entries"]), 1, "dsh 只有一个 project root")
        entry = m["entries"][0]
        self.assertEqual(entry["status"], "copied")
        self.assertEqual(entry["skill"], "kali-claw-kb")
        sha = entry["files_sha256"]
        self.assertIn("SKILL.md", sha)
        self.assertIn("kb/web-sqli.md", sha)
        self.assertEqual(len(sha["SKILL.md"]), 64)

    def test_second_staging_records_pre_existing_with_same_fingerprint(self):
        stage_extra_skills(self.workdir, engine="dsh")
        stage_extra_skills(self.workdir, engine="dsh")
        m = self._manifest()
        self.assertEqual(m["entries"][0]["status"], "pre_existing")
        first = json.loads((self.workdir / "skills-projection.json").read_text(
            encoding="utf-8"))
        # 同内容两次投影指纹一致（worker_skills 会覆盖 manifest，读的是第二次）
        self.assertEqual(first["entries"][0]["files_sha256"],
                         m["entries"][0]["files_sha256"])

    def test_unreadable_source_is_recorded_not_silent(self):
        os.environ["MUTEKI_EXTRA_SKILLS_DIR"] = str(
            self.src.parent / "does-not-exist")
        staged = stage_extra_skills(self.workdir, engine="dsh")
        self.assertEqual(staged, [])
        m = self._manifest()
        self.assertEqual(m["status"], "source_unavailable")
        self.assertIn("error", m)

    def test_copy_failure_is_recorded_with_stderr_warning(self):
        # 用 mock 在 OS 边界模拟 copytree 失败（如磁盘/权限错误）——预置同名
        # FILE 走的是"操作员内容保留"(pre_existing) 分支，不是失败分支。
        import contextlib
        import io
        from unittest import mock
        err = io.StringIO()
        with mock.patch("muteki.solver.worker_skills.shutil.copytree",
                        side_effect=OSError(13, "Permission denied")):
            with contextlib.redirect_stderr(err):
                staged = stage_extra_skills(self.workdir, engine="dsh")
        m = self._manifest()
        self.assertTrue(m["failures"], "复制失败必须记录")
        self.assertEqual(m["status"], "failed")
        self.assertIn("FAILED to stage skill", err.getvalue())
        self.assertIn("Permission denied", err.getvalue())
        # 失败条目不进入 staged
        self.assertNotIn(
            str(self.workdir / ".agents" / "skills" / "kali-claw-kb"), staged)

    def test_blocking_file_is_operator_content_not_failure(self):
        # 同名 FILE 已存在 = 操作员有意提供的内容，保留且记 pre_existing，
        # 不计入 failures（与"从不覆盖"策略一致）。
        blocker = self.workdir / ".agents" / "skills" / "kali-claw-kb"
        blocker.parent.mkdir(parents=True, exist_ok=True)
        blocker.write_text("operator content", encoding="utf-8")
        staged = stage_extra_skills(self.workdir, engine="dsh")
        m = self._manifest()
        self.assertEqual(m["status"], "ok")
        self.assertEqual(m["entries"][0]["status"], "pre_existing")
        self.assertEqual(m["failures"], [])
        self.assertIn(str(blocker), staged)


if __name__ == "__main__":
    unittest.main()
