"""A02 — a solved verdict must trace back to real accepted execution.

The harness used ``ch["flag"] in json.dumps(events)``: any occurrence of the flag
string in the event stream counted as solved.  A synthetic stream with only
``text.delta`` and no tool execution evaluated True.

These tests pin the evidence contract:
  * text-only mention (challenge text / hint / guess) is a CANDIDATE, not a solve;
  * acceptance without execution evidence is not trusted;
  * a rejected candidate never counts, however it was produced;
  * acceptance from a different attempt/generation does not carry over;
  * external verification is tracked separately and can satisfy the verdict.

Run:  python -X utf8 -B -m unittest tests.test_eval_verdict -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "labs" / "nyu-ctf"))

from eval_verdict import evaluate_attempt  # noqa: E402

FLAG = "flag{abc123}"


def ev(etype, seq, **payload):
    return {"event_type": etype, "seq": seq, "run_id": "r", "payload": payload}


def tool_output(seq, text, **extra):
    return ev("tool.result", seq, output=text, **extra)


def accepted(seq, flag=FLAG, **extra):
    return ev("flag.accepted", seq, flag=flag, status="accepted", **extra)


class TextMentionTests(unittest.TestCase):
    """题目/hint/猜测中出现答案不算解出。"""

    def test_text_delta_alone_is_not_solved(self):
        events = [ev("text.delta", 1, text=f"我猜答案是 {FLAG}")]
        v = evaluate_attempt(events, expected_flags=FLAG)
        self.assertFalse(v.solved)
        self.assertTrue(v.candidate_found)
        self.assertFalse(v.gate_accepted)
        self.assertFalse(v.execution_observed)

    def test_challenge_description_echo_is_not_solved(self):
        # The prompt containing the flag format must not self-qualify.
        events = [ev("run.started", 1, brief=f"find {FLAG}"),
                  ev("text.delta", 2, text="starting")]
        v = evaluate_attempt(events, expected_flags=FLAG)
        self.assertFalse(v.solved)

    def test_operator_hint_containing_flag_is_not_solved(self):
        events = [ev("text.delta", 1, text=f"hint: 试试 {FLAG}"),
                  ev("tool.start", 2, name="bash")]
        v = evaluate_attempt(events, expected_flags=FLAG)
        self.assertFalse(v.solved, "hint 中的答案不得判为解出")

    def test_worker_finished_text_is_not_solved(self):
        events = [ev("tool.result", 1, output="some output"),
                  ev("worker.finished", 2, text=f"答案是 {FLAG}")]
        v = evaluate_attempt(events, expected_flags=FLAG)
        self.assertFalse(v.solved)


class AcceptanceTests(unittest.TestCase):
    def test_real_execution_plus_acceptance_is_solved(self):
        events = [
            ev("tool.start", 1, name="bash"),
            tool_output(2, f"cat flag.txt -> {FLAG}"),
            accepted(3),
        ]
        v = evaluate_attempt(events, expected_flags=FLAG)
        self.assertTrue(v.solved)
        self.assertTrue(v.gate_accepted)
        self.assertTrue(v.execution_observed)

    def test_acceptance_without_execution_is_not_trusted(self):
        # A forged acceptance line with no tool output behind it.
        events = [accepted(1)]
        v = evaluate_attempt(events, expected_flags=FLAG)
        self.assertFalse(v.solved)
        self.assertIn("执行", v.reason)

    def test_rejected_candidate_never_counts(self):
        events = [
            ev("tool.start", 1, name="bash"),
            tool_output(2, f"try {FLAG}"),
            ev("flag.accepted", 3, flag=FLAG, status="rejected"),
        ]
        v = evaluate_attempt(events, expected_flags=FLAG)
        self.assertFalse(v.solved)
        self.assertTrue(v.candidate_found)
        self.assertEqual(v.rejected_candidates, 1)

    def test_candidate_without_acceptance_is_not_solved(self):
        events = [
            ev("tool.start", 1, name="bash"),
            tool_output(2, f"maybe {FLAG}"),
        ]
        v = evaluate_attempt(events, expected_flags=FLAG)
        self.assertFalse(v.solved)
        self.assertTrue(v.candidate_found)
        self.assertFalse(v.gate_accepted)


class AttemptScopingTests(unittest.TestCase):
    def test_acceptance_from_another_generation_is_ignored(self):
        events = [
            ev("tool.start", 1, name="bash"),
            tool_output(2, FLAG, execution_generation=2),
            accepted(3, execution_generation=2),
        ]
        v = evaluate_attempt(events, expected_flags=FLAG, attempt=1)
        self.assertFalse(v.solved, "上一次 attempt 的接受记录不得沿用")
        v2 = evaluate_attempt(events, expected_flags=FLAG, attempt=2)
        self.assertTrue(v2.solved)

    def test_attempt_matched_flag_is_reported(self):
        events = [ev("tool.start", 1, name="bash"),
                  tool_output(2, FLAG, execution_generation=1),
                  accepted(3, execution_generation=1)]
        v = evaluate_attempt(events, expected_flags=FLAG, attempt=1)
        self.assertTrue(v.attempt_matched)


class ExternalVerdictTests(unittest.TestCase):
    def test_external_judge_can_satisfy_without_local_acceptance(self):
        events = [ev("tool.start", 1, name="bash"), tool_output(2, "anything")]
        v = evaluate_attempt(events, expected_flags=FLAG,
                             accepted_flags=[FLAG])
        self.assertTrue(v.solved)
        self.assertTrue(v.external_verified)
        self.assertFalse(v.gate_accepted)

    def test_external_judge_disagreeing_does_not_solve(self):
        events = [ev("tool.start", 1, name="bash"), tool_output(2, "x")]
        v = evaluate_attempt(events, expected_flags=FLAG,
                             accepted_flags=["flag{other}"])
        self.assertFalse(v.solved)

    def test_multi_flag_tracking(self):
        events = [ev("tool.start", 1, name="bash"), tool_output(2, "x")]
        v = evaluate_attempt(events, expected_flags=["flag{a}", "flag{b}"],
                             accepted_flags=["flag{a}"])
        self.assertEqual(v.multi_flag_satisfied, {"flag{a}": True, "flag{b}": False})
        # Audit 5.3: multi-flag completion requires EVERY expected flag to be
        # externally confirmed — one of two must not score as solved.
        self.assertFalse(v.solved, "多 flag 需全部确认才算解出")

    def test_multi_flag_all_confirmed_solves(self):
        events = [ev("tool.start", 1, name="bash"), tool_output(2, "x")]
        v = evaluate_attempt(events, expected_flags=["flag{a}", "flag{b}"],
                             accepted_flags=["flag{a}", "flag{b}"])
        self.assertTrue(v.solved)


class DegenerateTests(unittest.TestCase):
    def test_no_flag_configured_is_explicit(self):
        v = evaluate_attempt([], expected_flags="")
        self.assertFalse(v.solved)
        self.assertIn("无法判定", v.reason)

    def test_no_events_is_not_solved(self):
        v = evaluate_attempt([], expected_flags=FLAG)
        self.assertFalse(v.solved)
        self.assertEqual(v.candidate_found, False)

    def test_verdict_is_json_serialisable(self):
        events = [ev("tool.start", 1, name="bash"), tool_output(2, FLAG),
                  accepted(3)]
        v = evaluate_attempt(events, expected_flags=FLAG)
        text = json.dumps(v.to_dict(), ensure_ascii=False)
        self.assertIn("candidate_found", text)


class ArchivedRunTests(unittest.TestCase):
    """run-20670 was NOT solved; the new verdict must not flip it."""

    LOG = ROOT / "data" / "sessions" / "run-20670.jsonl"

    def setUp(self):
        if not self.LOG.is_file():
            self.skipTest("run-20670.jsonl 不在本地")

    def test_unsolved_run_stays_unsolved(self):
        from usage_reduce import read_events  # local import: shared helper
        events = read_events(self.LOG)
        # The harness knows the official flag for this challenge; either way an
        # unsolved run must not become solved.
        v = evaluate_attempt(events, expected_flags="flag{anything}")
        self.assertFalse(v.solved)




class Batch6ATests(unittest.TestCase):
    """批次 6A：多 Flag 时序、artifact 代次、路径穿越、字节摘要。"""

    def test_multi_flag_per_flag_temporal_binding(self):
        """第二枚 Flag 的输出在第一枚接受之后出现时仍是合法证据。

        旧实现取全局最早接受 seq 截断输出，导致双 Flag 串行求解被误判
        （核查报告 4.1 复现例）。"""
        events = [
            tool_output(10, f"exploit output contains {FLAG}"),
            accepted(11),
            tool_output(20, "second output contains flag{second}"),
            ev("flag.accepted", 21, flag="flag{second}", status="accepted"),
            ev("run.finished", 30, solved=True, flags=[FLAG, "flag{second}"]),
        ]
        v = evaluate_attempt(events, expected_flags=[FLAG, "flag{second}"])
        self.assertTrue(v.solved)
        self.assertTrue(v.solved)
        self.assertTrue(v.gate_accepted)
        self.assertEqual(v.unlinked_flags, [])

    def test_artifact_generation_uncertainty_propagates(self):
        """artifact 命中分支也必须传播代次不确定性（旧实现仅 inline 分支更新）。"""
        events = [
            {"event_type": "tool.result", "seq": 10,
             "payload": {"result": "see artifact",
                         "artifact_id": "abc123",
                         # 无 generation：代次未知
                         }},
            accepted(11),
        ]
        import tempfile
        arts = tempfile.mkdtemp()
        (Path(arts) / "abc123.txt").write_text(f"tail of output: {FLAG}",
                                               encoding="utf-8")
        v = evaluate_attempt(events, expected_flags=FLAG, attempt=2,
                             artifacts_dir=arts)
        self.assertTrue(v.gate_accepted)
        self.assertFalse(v.attempt_matched, "gen-uncertain must not claim match")

    def test_artifact_traversal_is_rejected(self):
        """artifact_id 含 ../ 或绝对路径时必须拒绝读取，不得命中 arts 外文件。"""
        import tempfile
        events = [
            {"event_type": "tool.result", "seq": 10,
             "payload": {"result": "see artifact",
                         "artifact_id": "../outside"}},
            accepted(11),
        ]
        outside = tempfile.mkdtemp()
        secret = Path(outside) / "outside.txt"
        secret.write_text(FLAG, encoding="utf-8")
        arts = tempfile.mkdtemp()
        v = evaluate_attempt(events, expected_flags=FLAG, attempt=None,
                             artifacts_dir=arts)
        self.assertFalse(v.solved)
        secret.unlink()

    def test_artifact_sha_is_raw_bytes(self):
        """sha256 必须等于原始文件字节摘要（CRLF 不被规范化）。"""
        import hashlib
        import tempfile
        events = [
            {"event_type": "tool.result", "seq": 10,
             "payload": {"result": "see artifact", "artifact_id": "art1"}},
            accepted(11),
        ]
        arts = tempfile.mkdtemp()
        body = b"line1\r\nline2\r\nflag tail: " + FLAG.encode()
        target = Path(arts) / "art1.txt"
        target.write_bytes(body)
        v = evaluate_attempt(events, expected_flags=FLAG, attempt=None,
                             artifacts_dir=arts)
        raw_sha = hashlib.sha256(body).hexdigest()
        links = [l for l in v.evidence_links if l.get("sha256")]
        self.assertTrue(links, "evidence link with sha expected")
        self.assertEqual(links[0]["sha256"], raw_sha)

    def test_no_path_traversal_reading_outside(self):
        """"../outside" 形态的 artifact_id 不得读取 arts 外文件。"""
        import tempfile
        events = [
            {"event_type": "tool.result", "seq": 10,
             "payload": {"result": "see artifact", "artifact_id": "../esc"}},
            accepted(11),
        ]
        outside_dir = tempfile.mkdtemp()
        (Path(outside_dir) / "esc.txt").write_text(FLAG, encoding="utf-8")
        arts = tempfile.mkdtemp()
        v = evaluate_attempt(events, expected_flags=FLAG, attempt=None,
                             artifacts_dir=arts)
        self.assertFalse(v.solved)
        self.assertTrue(v.unlinked_flags or not v.gate_accepted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
