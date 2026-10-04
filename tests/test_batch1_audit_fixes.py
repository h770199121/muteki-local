"""第一批核查修复的宿主侧回归（2026-10-04 audit 5.3 / 5.4 / 5.6）。

对应 docs/项目进展核查与下一步优先级-2026-10-04.md：
  * 5.3 A02 —— 官方 flag 存在时 gate 不回退（run_challenge._eval_solved 真实导入）；
  * 5.4 A01 —— 归约完整性按覆盖关系判定（usage_reduce 真实导入，audit 三行夹具；
    两行同账本/超账本的新增断言见 tests/test_usage_reduce.py）；
  * 5.6 —— 拒绝 Hello 的 stderr 不含凭据内容（真实 ControlReceiver._handshake +
    socketpair，捕获 stderr 断言）。

5.1 的 mixin 消费路径与 5.5 的 CostController.record 依赖 pydantic 宿主不可导入，
在 tests/container_batch1_audit_fixes.py 于产品镜像内以真实依赖执行。

Run:  python -X utf8 -B -m unittest tests.test_batch1_audit_fixes -v
"""

from __future__ import annotations

import contextlib
import io
import json
import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "labs" / "nyu-ctf"))

from eval_verdict import evaluate_attempt  # noqa: E402
from run_challenge import _eval_solved, _gate_solved  # noqa: E402
from usage_reduce import reduce_usage  # noqa: E402


def cost_event(seq, scope, identity, in_tok, out_tok):
    return {
        "event_type": "cost.update", "seq": seq, "ts": 1791000000.0 + seq,
        "run_id": "run-x", "challenge_id": "run-x",
        "payload": {"scope": scope, "identity": identity,
                    "input_tokens": in_tok, "output_tokens": out_tok,
                    "usd": 0.0, "execution_generation": 1},
    }


# ── 5.3: official flag stays authoritative ───────────────────────────────────

class EvalSolvedRoutingTests(unittest.TestCase):
    def test_known_flag_mismatch_with_gate_is_not_solved(self):
        # audit 5.3 夹具：gate 接受了 flag{wrong}，官方值 flag{expected} ——
        # 无条件的 `verdict.solved or gate_solved` 会把这场误判为解出。
        verdict = type("V", (), {"solved": False})()
        self.assertFalse(_eval_solved(verdict, gate_solved=True,
                                      official=["flag{expected}"]))

    def test_no_official_flag_still_requires_evidence(self):
        # Batch-4-1 收敛：gate fallback 也必须走证据管线——verdict.solved=false
        # （gate flag 回查不到真实输出）时不得被 gate_solved 救回。
        verdict = type("V", (), {"solved": False})()
        self.assertFalse(_eval_solved(verdict, gate_solved=True, official=[]))

    def test_gate_derived_flag_with_evidence_solves(self):
        # 无官方 flag：RUN_FINISHED(solved=true) 给出候选，且同 flag 出现在
        # 真实 tool.result 输出中 → 证据成立，判解出。
        events = [
            {"event_type": "tool.result", "seq": 5,
             "payload": {"result": {"condensed": "flag page: CTF2{x}"}}},
            {"event_type": "run.finished", "seq": 9,
             "payload": {"solved": True, "flag": "CTF2{x}"}},
        ]
        v = evaluate_attempt(events, expected_flags="")
        self.assertTrue(v.solved)
        self.assertTrue(v.evidence_links)

    def test_gate_derived_flag_without_output_is_rejected(self):
        # 无官方 flag：终态声称解出但输出中找不到 flag（截断/无落盘）→ 不解出，
        # 且记录 unlinked 原因。
        events = [
            {"event_type": "tool.result", "seq": 5,
             "payload": {"result": {"condensed": "login page, no flag here"}}},
            {"event_type": "run.finished", "seq": 9,
             "payload": {"solved": True, "flag": "CTF2{x}"}},
        ]
        v = evaluate_attempt(events, expected_flags="")
        self.assertFalse(v.solved)
        self.assertIn("CTF2{x}", v.unlinked_flags)

    def test_command_field_flag_is_not_output_evidence(self):
        # batch-4-1①：flag 只出现在命令字段（worker 输入）而非响应输出时，
        # 不得作为"真实输出"证据。
        events = [
            {"event_type": "tool.result", "seq": 5,
             "payload": {"tool": "bash: submit-flag 'CTF2{x}'",
                         "result": {"condensed": "OK wrote verified fact"}}},
            {"event_type": "run.finished", "seq": 9,
             "payload": {"solved": True, "flag": "CTF2{x}"}},
        ]
        v = evaluate_attempt(events, expected_flags="CTF2{x}")
        self.assertFalse(v.gate_accepted)
        self.assertFalse(v.solved)

    def test_generation_binding_output_vs_acceptance(self):
        # batch-4-1④：attempt=2 时，第 1 代的输出不能作为第 2 代接受的证据。
        events = [
            {"event_type": "tool.result", "seq": 5, "execution_generation": 1,
             "payload": {"output": "CTF2{x}", "execution_generation": 1}},
            {"event_type": "flag.accepted", "seq": 6, "execution_generation": 2,
             "payload": {"flag": "CTF2{x}", "status": "accepted",
                         "execution_generation": 2}},
        ]
        v = evaluate_attempt(events, expected_flags="CTF2{x}", attempt=2)
        self.assertFalse(v.gate_accepted)
        self.assertFalse(v.solved)

    def test_known_flag_match_still_solves(self):
        verdict = type("V", (), {"solved": True})()
        self.assertTrue(_eval_solved(verdict, gate_solved=False,
                                     official=["flag{expected}"]))

    def test_gate_verdict_traces_to_real_run_finished(self):
        events = [{"event_type": "run.finished",
                   "payload": {"solved": True, "flag": "CTF2{x}"}}]
        self.assertTrue(_gate_solved(events))
        self.assertFalse(_gate_solved([]))

    def test_multi_flag_partial_external_confirmation_is_not_solved(self):
        events = [{"event_type": "tool.start", "payload": {"tool": "bash"}}]
        v = evaluate_attempt(events, expected_flags=["flag{a}", "flag{b}"],
                             accepted_flags=["flag{a}"])
        self.assertFalse(v.solved)

    def test_multi_flag_all_confirmed_solves(self):
        events = [{"event_type": "tool.start", "payload": {"tool": "bash"}}]
        v = evaluate_attempt(events, expected_flags=["flag{a}", "flag{b}"],
                             accepted_flags=["flag{a}", "flag{b}"])
        self.assertTrue(v.solved)


# ── 5.4: reduction honesty — the audit's three-row fixture ───────────────────

class ReductionCoverageTests(unittest.TestCase):
    def test_equal_rollup_agrees_and_is_complete(self):
        events = [
            cost_event(1, "solver", "a", 100, 10),
            cost_event(2, "challenge", "run-x", 100, 10),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.basis, "solver_ledgers")
        self.assertEqual(r.input_tokens, 100)
        self.assertTrue(r.telemetry_complete,
                        "rollup 与 solver 台账一致时应判定为完整")

    def test_rollup_bigger_and_newer_is_authoritative_total(self):
        # 批次 2 细化（audit 5.4）：rollup 序号更新且更大 = 超集（含
        # challenge-scope 独有调用），是权威完整总量。
        events = [
            cost_event(1, "solver", "a", 100, 10),
            cost_event(2, "challenge", "run-x", 150, 15),
        ]
        r = reduce_usage(events)
        self.assertEqual(r.basis, "challenge_rollup")
        self.assertEqual(r.input_tokens, 150)
        self.assertTrue(r.telemetry_complete)

    def test_rollup_smaller_and_stale_is_incomplete(self):
        events = [
            cost_event(1, "solver", "a", 100, 10),
            cost_event(2, "challenge", "run-x", 50, 5),
        ]
        r = reduce_usage(events)
        self.assertFalse(r.telemetry_complete)


# ── 5.6: rejected-Hello log must not leak token material ─────────────────────

class HandshakeLogHygieneTests(unittest.TestCase):
    def test_rejected_hello_logs_lengths_not_material(self):
        from muteki.solver.control_receiver import ControlReceiver
        recv = ControlReceiver(host="127.0.0.1", port=0)
        expected = "a" * 64
        recv.expect("run-log-1", expected)
        client, server = socket.socketpair()
        client.sendall((json.dumps({"run_id": "run-log-1",
                                    "token": "b" * 64}) + "\n").encode())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            recv._handshake(server, ("127.0.0.1", 0))
        out = err.getvalue()
        self.assertIn("hello REJECTED", out)
        self.assertIn("token_matches=False", out)
        self.assertNotIn("token_prefix", out, "不得输出凭据片段")
        self.assertNotIn(expected[:8], out, "预期 token 片段不得入日志")
        self.assertNotIn("b" * 8, out, "实际 token 片段不得入日志")
        # 客户端仍收到结构化拒绝
        reply = json.loads(client.recv(4096).decode())
        self.assertFalse(reply["ok"])


if __name__ == "__main__":
    unittest.main()
