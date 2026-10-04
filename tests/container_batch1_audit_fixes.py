"""第一批核查修复的镜像内回归：5.1 mixin 消费路径 + 5.5 record 裁定金额。

宿主 venv 缺 pydantic，无法导入 muteki.swarm.coordinator_dispatch 与
muteki.core.cost —— 本脚本在产品镜像（.venv 含产品依赖）内以真实导入执行，
对应 docs/项目进展核查与下一步优先级-2026-10-04.md 第 7 节"新增测试应调用
实际消费路径"的要求。

Run (from repo root, mirrors the audit's container command shape):
  docker run --rm --pull never --network none --read-only --tmpfs /tmp \\
    --mount src=D:\\AI\\muteki-local\\muteki,dst=/audit/muteki,readonly \\
    --mount src=D:\\AI\\muteki-local\\tests,dst=/audit/tests,readonly \\
    --workdir /audit --env PYTHONPATH=/audit --env PYTHONDONTWRITEBYTECODE=1 \\
    --entrypoint /app/.venv/bin/python muteki-web:latest -B \\
    tests/container_batch1_audit_fixes.py
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from muteki.swarm.coordinator_dispatch import _DispatchReasonMixin
from muteki.swarm.dispatch_failure_governor import FailureGovernor
from muteki.core.cost import CostController, ModelPrice


class _StubCoordinator(_DispatchReasonMixin):
    """Real mixin + minimal state, exactly what the method body touches."""

    def __init__(self):
        self._dispatch_failure_governor = FailureGovernor(limit=3)
        self._dispatch_failure_limit_reached = False
        self._live_solvers = {}
        self.events: list[tuple[str, dict]] = []
        self.cancelled: list[str] = []

    async def _emit_coord_bb(self, kind, **fields):
        self.events.append((kind, fields))

    def _cancel_solver(self, solver):
        self.cancelled.append(str(getattr(solver, "solver_id", "")))


class D04ProductionWiringTests(unittest.TestCase):
    def test_forced_free_text_rejection_is_counted(self):
        stub = _StubCoordinator()
        asyncio.run(stub._note_worker_dispatch_failure({
            "reason": "StartWorker rejected: fork/exec /usr/bin/python3: "
                      "operation not permitted",
            "engine": "dsh",
        }, force_prestart=True))
        self.assertEqual(stub._dispatch_failure_governor.consecutive, 1,
                         "pre-start 死亡必须计入")

    def test_capacity_rejection_is_never_counted(self):
        stub = _StubCoordinator()
        asyncio.run(stub._note_worker_dispatch_failure(
            {"reason": "max_workers"}, force_prestart=True))
        asyncio.run(stub._note_worker_dispatch_failure(
            {"reason": "profile_capacity"}, force_prestart=True))
        self.assertEqual(stub._dispatch_failure_governor.consecutive, 0)
        self.assertFalse(stub._dispatch_failure_limit_reached)

    def test_live_started_solver_is_credited_once_only(self):
        stub = _StubCoordinator()
        started = SimpleNamespace(solver_id="cli-dsh-1",
                                  _runtime_process_started=True,
                                  _control_context_delivery_committed=False,
                                  _control_context_delivery_unknown=False,
                                  done=lambda: False)
        stub._live_solvers["cli-dsh-1"] = started
        for _ in range(2):
            asyncio.run(stub._note_worker_dispatch_failure(
                {"reason": "provider_config_missing", "engine": "dsh"}))
        gov = stub._dispatch_failure_governor
        # 旧实现：每次拒绝都拿同一个存活 solver 重新清零 → 计数恒为 1，永远到不了上限。
        self.assertEqual(gov.consecutive, 2, "启动凭据只消费一次，后续拒绝必须累加")

    def test_limit_reached_sets_flag_cancels_and_names_cause(self):
        stub = _StubCoordinator()
        dying = SimpleNamespace(solver_id="cli-dsh-2",
                                _runtime_process_started=False,
                                _control_context_delivery_committed=False,
                                _control_context_delivery_unknown=False,
                                done=lambda: False)
        stub._live_solvers["cli-dsh-2"] = dying
        for _ in range(3):
            asyncio.run(stub._note_worker_dispatch_failure({
                "reason": "container_setup_failed", "engine": "dsh",
                "detail": "container backend is unavailable",
            }, force_prestart=True))
        self.assertTrue(stub._dispatch_failure_limit_reached)
        gov = stub._dispatch_failure_governor
        self.assertTrue(gov.limit_reached)
        self.assertIn("3 consecutive Worker dispatches failed before process start",
                      gov.stop_reason())
        self.assertIn("worker_dispatch_failure_limit",
                      [k for k, _ in stub.events])
        self.assertIn("cli-dsh-2", stub.cancelled, "达上限后应取消存活 solver")


class RecordAdjudicationTests(unittest.TestCase):
    def _controller(self, extra_prices=None):
        ctl = CostController()
        for name, price in (extra_prices or {}).items():
            ctl.prices[name] = price
        return ctl

    def test_local_endpoint_with_configured_price_bills_zero(self):
        # Audit 5.5 fixture: a localhost-model WITH a table rate used to be billed
        # the rate by Ledger.add while price_usage reported local_zero_api_cost.
        ctl = self._controller({"localhost-model": ModelPrice(
            input_per_m=1.0, output_per_m=3.0)})
        usd = asyncio.run(ctl.record(
            model="localhost-model", input_tokens=1_000_000,
            output_tokens=0, run_id="r"))
        self.assertEqual(usd, 0.0, "本地模型裁定为无 API 费用，账本不得计费")
        self.assertEqual(ctl._global.usd, 0.0)
        self.assertEqual(ctl._global.input_tokens, 1_000_000, "token 仍需计数")

    def test_endpoint_authoritative_over_model_name(self):
        ctl = self._controller()
        usd = asyncio.run(ctl.record(
            model="qwen3.8-27b", input_tokens=500, output_tokens=50,
            run_id="r", endpoint="http://host.docker.internal:18210/v1"))
        self.assertEqual(usd, 0.0, "本地 endpoint 判定不依赖模型名")
        usd2 = asyncio.run(ctl.record(
            model="qwen3.8-27b", input_tokens=10, output_tokens=1, run_id="r",
            endpoint="https://api.example.com/v1"))
        self.assertEqual(usd2, 0.0)
        self.assertEqual(ctl.unpriced_calls, 1, "未定价计入 unpriced_calls")

    def test_exact_price_still_bills_real_rates(self):
        if "deepseek-v4-flash" not in CostController().prices:
            self.skipTest("PRICES 表无 deepseek-v4-flash")
        ctl = self._controller()
        usd = asyncio.run(ctl.record(
            model="deepseek-v4-flash", input_tokens=1_000_000,
            output_tokens=1_000_000, run_id="r",
            endpoint="https://api.deepseek.com/v1"))
        self.assertGreater(usd, 0.0, "已知费率 + 云端 endpoint 必须真实计费")
        self.assertAlmostEqual(ctl._global.usd, usd, places=9)

    def test_all_ledgers_share_the_adjudicated_amount(self):
        ctl = self._controller({"localhost-model": ModelPrice(
            input_per_m=2.0, output_per_m=2.0)})
        asyncio.run(ctl.record(
            model="localhost-model", input_tokens=1_000_000, output_tokens=0,
            run_id="r", challenge_id="c1", solver_id="s1"))
        self.assertEqual(ctl._global.usd, 0.0)
        self.assertEqual(ctl._by_challenge["c1"].usd, 0.0)
        self.assertEqual(ctl._by_solver["s1"].usd, 0.0)
        # token 计数三个账本一致
        self.assertEqual(ctl._global.input_tokens, 1_000_000)
        self.assertEqual(ctl._by_solver["s1"].input_tokens, 1_000_000)


if __name__ == "__main__":
    unittest.main()
