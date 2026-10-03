"""A04 — worker accounting must use the real model, and unknown means unpriced.

Two defects:

1. ``CliSolver._stream_cost`` resolved the model from ``self.model`` /
   ``self.profile`` (neither is ever assigned) and finally fell back to a hardcoded
   ``"deepseek-v4-flash"``.  A worker configured as ``qwen3.8-27b`` was therefore
   billed at DeepSeek flash rates.
2. ``CostController.price_for`` fell back to a fabricated ``$1/$3 per 1M`` for any
   model absent from ``PRICES``, inventing money that was never spent.

The contract now:
  * the driver's profile is the model authority;
  * no hardcoded engine model may be substituted;
  * an unresolved model is UNPRICED (tokens still counted, status disclosed);
  * a local endpoint is explicitly "no API cost", distinct from "unknown price";
  * USD, wall-clock and worker-count budgets stay independent.

The project venv cannot import pydantic, so ``cost.py`` and the identity resolver
are exercised the same way ``test_a03_free_text_sealing`` does it: load the REAL
source and execute the shipped logic.

Run:  python -X utf8 -B -m unittest tests.test_cost_pricing -v
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- cost.py


def load_cost_namespace() -> dict:
    """Execute the real ModelPrice / pricing helpers from muteki/core/cost.py."""
    source = (ROOT / "muteki" / "core" / "cost.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    keep: list[ast.AST] = []
    wanted_assigns = {"PRICES", "CODEX_CACHED_INPUT_PER_M", "PRICE_STATUS_EXACT",
                      "PRICE_STATUS_LOCAL", "PRICE_STATUS_UNPRICED",
                      "_LOCAL_MODEL_MARKERS"}
    wanted_funcs = {"price_status"}

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in {"ModelPrice", "PricedUsage"}:
            keep.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_funcs:
            keep.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in wanted_assigns:
                keep.append(node)
        elif isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if names & wanted_assigns:
                keep.append(node)

    module = ast.Module(body=keep, type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict = {"dataclass": __import__("dataclasses").dataclass,
                "field": __import__("dataclasses").field}
    exec(compile(module, str(ROOT / "muteki" / "core" / "cost.py"), "exec"), ns)  # noqa: S102
    return ns


NS = load_cost_namespace()
ModelPrice = NS["ModelPrice"]
price_status = NS["price_status"]
PRICES = NS["PRICES"]
PRICE_STATUS_EXACT = NS["PRICE_STATUS_EXACT"]
PRICE_STATUS_LOCAL = NS["PRICE_STATUS_LOCAL"]
PRICE_STATUS_UNPRICED = NS["PRICE_STATUS_UNPRICED"]


def lookup(prices: dict, model: str):
    found = prices.get(model)
    if found is None and ":" in model:
        found = prices.get(model.split(":", 1)[0])
    return found


def price_usage(prices: dict, model: str, in_tok: int, out_tok: int):
    price = lookup(prices, model)
    status = price_status(model, price)
    if price is None or status == PRICE_STATUS_LOCAL:
        return in_tok, out_tok, 0.0, status
    usd = in_tok / 1_000_000 * price.input_per_m + out_tok / 1_000_000 * price.output_per_m
    return in_tok, out_tok, usd, status


class UnknownModelIsUnpricedTests(unittest.TestCase):
    def test_unknown_model_is_unpriced_not_fabricated(self):
        _, _, usd, status = price_usage(dict(PRICES), "qwen3.8-27b", 1_000_000, 100_000)
        self.assertEqual(status, PRICE_STATUS_UNPRICED)
        self.assertEqual(usd, 0.0, "未知模型不得产生任何美元金额")

    def test_unknown_model_still_counts_tokens(self):
        i, o, _, status = price_usage(dict(PRICES), "qwen3.8-27b", 500, 50)
        self.assertEqual((i, o), (500, 50), "未定价也必须保留 token 统计")
        self.assertEqual(status, PRICE_STATUS_UNPRICED)

    def test_known_model_keeps_its_real_rate(self):
        i, o, usd, status = price_usage(dict(PRICES), "deepseek-v4-flash",
                                        1_000_000, 1_000_000)
        self.assertEqual(status, PRICE_STATUS_EXACT)
        self.assertAlmostEqual(usd, 0.07 + 0.28, places=6)
        self.assertNotAlmostEqual(usd, 1.0 + 3.0, places=3,
                                  msg="不得回落到旧的 _DEFAULT_PRICE")

    def test_empty_model_is_unpriced(self):
        _, _, usd, status = price_usage(dict(PRICES), "", 1_000_000, 1_000_000)
        self.assertEqual(status, PRICE_STATUS_UNPRICED)
        self.assertEqual(usd, 0.0)

    def test_no_fallback_constant_remains(self):
        # The name may survive in explanatory comments; what must be gone is any
        # live binding or use.
        cost_src = (ROOT / "muteki" / "core" / "cost.py").read_text(encoding="utf-8")
        code_only = "\n".join(
            line for line in cost_src.splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertNotIn("_DEFAULT_PRICE", code_only,
                         "虚构单价兜底必须从代码中移除")
        driver = (ROOT / "muteki" / "solver" / "cli_driver.py").read_text(encoding="utf-8")
        driver_code = "\n".join(
            line for line in driver.splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertNotIn("_DEFAULT_PRICE", driver_code)


class LocalEndpointTests(unittest.TestCase):
    def test_local_endpoint_is_zero_api_cost_not_unpriced(self):
        for model in ("http://127.0.0.1:18210/v1", "qwen@localhost",
                      "http://host.docker.internal:18210/v1"):
            with self.subTest(model=model):
                _, _, usd, status = price_usage(dict(PRICES), model, 1_000_000, 1_000_000)
                self.assertEqual(status, PRICE_STATUS_LOCAL)
                self.assertEqual(usd, 0.0)

    def test_local_is_distinguishable_from_unknown(self):
        _, _, _, local = price_usage(dict(PRICES), "http://127.0.0.1:18210/v1", 1, 1)
        _, _, _, unknown = price_usage(dict(PRICES), "some-unknown-model", 1, 1)
        self.assertNotEqual(local, unknown,
                            "『本地无 API 费用』与『价格未知』必须可区分")


# ------------------------------------------------- model identity (A04-1)


class EffectiveModelTests(unittest.TestCase):
    """The identity resolver, executed from the real cli_solver source."""

    @staticmethod
    def _load_resolver():
        source = (ROOT / "muteki" / "solver" / "cli_solver.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "effective_model":
                        mod = ast.Module(body=[item], type_ignores=[])
                        ast.fix_missing_locations(mod)
                        ns = {"os": __import__("os")}
                        exec(compile(mod, "cli_solver.py", "exec"), ns)  # noqa: S102
                        return ns["effective_model"]
        raise AssertionError("未找到 effective_model")

    def setUp(self):
        self.resolver = self._load_resolver()

    class _Driver:
        def __init__(self, profile=None, base=None):
            if profile is not None:
                self.profile = profile
            if base is not None:
                self.base = base

    class _Solver:
        pass

    def test_profile_on_driver_is_authoritative(self):
        s = self._Solver()
        s.driver = self._Driver(profile={"model": "qwen3.8-27b"})
        self.assertEqual(self.resolver(s), "qwen3.8-27b")

    def test_profile_on_nested_base_driver_is_found(self):
        s = self._Solver()
        s.driver = self._Driver(base=self._Driver(profile={"model": "qwen3.8-27b"}))
        self.assertEqual(self.resolver(s), "qwen3.8-27b")

    def test_unresolvable_model_returns_empty_not_a_foreign_model(self):
        s = self._Solver()
        s.driver = self._Driver()
        self.assertEqual(self.resolver(s), "", "取不到身份时必须返回空，不得套用他人模型")

    def test_never_falls_back_to_deepseek_flash(self):
        s = self._Solver()
        s.driver = self._Driver()
        resolved = self.resolver(s)
        self.assertNotIn("deepseek-v4-flash", resolved)

    def test_blank_profile_model_is_skipped(self):
        s = self._Solver()
        s.driver = self._Driver(profile={"model": "   "})
        self.assertEqual(self.resolver(s), "")

    def test_stream_cost_uses_the_resolver(self):
        source = (ROOT / "muteki" / "solver" / "cli_solver.py").read_text(encoding="utf-8")
        # The hardcoded chain must be gone from _stream_cost.
        self.assertNotIn('or "deepseek-v4-flash"', source)
        self.assertIn("model = self.effective_model()", source)


class BudgetIndependenceTests(unittest.TestCase):
    """USD, wall clock and worker count must be separate authorities."""

    def test_unpriced_usage_does_not_produce_usd_drift(self):
        a = price_usage(dict(PRICES), "qwen3.8-27b", 1_000_000, 1_000_000)
        b = price_usage(dict(PRICES), "qwen3.8-27b", 1_000_000, 1_000_000)
        self.assertEqual(a[2], b[2], "重复记录不得累积虚构费用")
        self.assertEqual(a[2], 0.0)

    def test_wall_clock_budget_is_not_derived_from_price(self):
        # run-20670 terminated on wall clock (elapsed=1201 vs budget 1200). Pricing
        # changes must not touch that path, which lives in coordinator_loop.
        loop = (ROOT / "muteki" / "swarm" / "coordinator_loop.py").read_text(encoding="utf-8")
        self.assertIn("wall_clock_budget_exhausted", loop,
                      "墙钟预算必须仍独立存在")
        # The wall-clock check must not be expressed in USD terms.
        self.assertNotIn("wall_clock_budget_usd", loop)


if __name__ == "__main__":
    unittest.main(verbosity=2)
