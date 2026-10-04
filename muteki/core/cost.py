"""Cost controller — real-time token/$ accounting per solver / challenge / global.

Feeds two things:
- L0 scheduler circuit-breaker (`over_budget(scope)`) — §4.2.
- The North Star metric `points per dollar-hour` — §12.

Prices are per-model, per-1M-tokens, configurable. The numbers below are
placeholders for the temporary DeepSeek endpoint; correctness lives in the
accounting, not the exact rate. Update PRICES when real rates are known.
"""

from __future__ import annotations

import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Optional

from muteki.core.event_bus import EventBus
from muteki.core.events import Event, EventType, cost_payload


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1M tokens."""

    input_per_m: float
    output_per_m: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1_000_000 * self.input_per_m
            + output_tokens / 1_000_000 * self.output_per_m
        )


# Placeholder price table. Reasoning tokens bill as output tokens.
PRICES: dict[str, ModelPrice] = {
    "deepseek-v4-pro": ModelPrice(input_per_m=0.55, output_per_m=2.19),
    "deepseek-v4-flash": ModelPrice(input_per_m=0.07, output_per_m=0.28),
    # codex (GPT-5 class) — subscription CLIs no longer report total_cost_usd,
    # so we re-derive an API-EQUIVALENT cost from the tokens it does report (the
    # same "what would this have cost on the API" lens we keep for claude). GPT-5
    # list price per 1M: input $1.25, output $10.00 (reasoning bills as output).
    # Cached input ($0.125/M) is folded into input here; cli_driver discounts it.
    "codex": ModelPrice(input_per_m=1.25, output_per_m=10.0),
    "gpt-5": ModelPrice(input_per_m=1.25, output_per_m=10.0),
}
# Ollama serves the same models under a ``:cloud`` tag and bills GPU-time, not
# tokens. Keep the DeepSeek list rates so a serving-stack switch does not silently
# reprice every run against _DEFAULT_PRICE (~14x on flash) and blow the budget gate.
PRICES.update(
    {f"{name}:cloud": price for name, price in list(PRICES.items())}
)
# Cached-input rate for codex/GPT-5 (per 1M). cli_driver prices cached tokens at
# this rate and fresh tokens at the full input rate when computing codex cost.
CODEX_CACHED_INPUT_PER_M = 0.125

# A04: an unknown model is UNPRICED, not free and not some other model's rate.
#
# The previous fallback (_DEFAULT_PRICE = $1/$3 per 1M) invented a dollar figure for
# every model absent from PRICES — a local qwen3.8-27b worker was billed at
# deepseek rates.  That is wrong in both directions: it never matches the real bill
# and it makes a USD budget gate fire on money that was never spent.  Setting the
# price to zero is equally wrong: $0 reads as "free" and hides the fact that the
# price is simply unknown.
#
# Instead, unpriced usage keeps its token accounting and is reported as unpriced.
PRICE_STATUS_EXACT = "exact"
PRICE_STATUS_LOCAL = "local_zero_api_cost"
PRICE_STATUS_UNPRICED = "unpriced"

#: Model identifiers served by a local runtime: real inference cost is electricity,
#: which we deliberately do NOT invent a dollar figure for.  They are tracked by
#: token count and reported as "no API cost", distinct from "unknown price".
_LOCAL_MODEL_MARKERS = (
    "localhost", "127.0.0.1", "host.docker.internal", "::1",
)


def price_status(model: str, price: "ModelPrice | None",
                 endpoint: str | None = None) -> str:
    """Classify how a model's usage should be accounted.

    ``local_zero_api_cost``  a local endpoint — no API bill exists
    ``exact``                a known list price
    ``unpriced``             no price is known; do not invent one

    Audit 5.5: when the caller knows the ACTUAL endpoint (base_url of the bound
    profile), it is authoritative — a model id like ``qwen3.8-27b`` carries no
    locality information and was previously classified by scanning the model
    string alone. The model-string markers remain as a fallback for callers
    that only have the name.
    """
    name = (model or "").strip().lower()
    ep = (endpoint or "").strip().lower()
    if not name and not ep:
        return PRICE_STATUS_UNPRICED
    if ep and any(marker in ep for marker in _LOCAL_MODEL_MARKERS):
        return PRICE_STATUS_LOCAL
    if any(marker in name for marker in _LOCAL_MODEL_MARKERS):
        return PRICE_STATUS_LOCAL
    if price is None:
        return PRICE_STATUS_UNPRICED
    return PRICE_STATUS_EXACT


@dataclass
class PricedUsage:
    """A usage record plus how its dollar figure was derived."""

    input_tokens: int
    output_tokens: int
    usd: float
    status: str
    model: str

    @property
    def priced(self) -> bool:
        return self.status != PRICE_STATUS_UNPRICED


@dataclass
class Ledger:
    usd: float = 0.0
    tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, price: ModelPrice, input_tokens: int, output_tokens: int) -> float:
        c = price.cost(input_tokens, output_tokens)
        self.usd += c
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.tokens += input_tokens + output_tokens
        self.calls += 1
        return c

    def add_adjudicated(self, priced: "PricedUsage") -> float:
        """Bump this ledger with an ALREADY-PRICED usage record (audit 5.5).

        The dollar figure comes from price_usage's adjudication — a local or
        unpriced model contributes 0 USD even when a table entry exists, while
        tokens are still counted. Callers must not bypass this by calling add()
        with a raw price: that is how a localhost model with a configured rate
        ended up billed real dollars while price_usage reported zero.
        """
        self.usd += float(priced.usd)
        self.input_tokens += int(priced.input_tokens)
        self.output_tokens += int(priced.output_tokens)
        self.tokens += int(priced.input_tokens) + int(priced.output_tokens)
        self.calls += 1
        return float(priced.usd)


@dataclass
class Budget:
    """USD ceilings per scope. None == unlimited."""

    global_usd: Optional[float] = None
    per_challenge_usd: Optional[float] = None
    per_solver_usd: Optional[float] = None


@dataclass
class CostController:
    bus: Optional[EventBus] = None
    budget: Budget = field(default_factory=Budget)
    prices: dict[str, ModelPrice] = field(default_factory=lambda: dict(PRICES))
    started_at: float = field(default_factory=time.time)

    _global: Ledger = field(default_factory=Ledger)
    _by_challenge: dict[str, Ledger] = field(default_factory=dict)
    _by_solver: dict[str, Ledger] = field(default_factory=dict)
    _usage_windows: dict[str, Ledger] = field(default_factory=dict)
    #: A04: number of calls whose model had no known price. Surfaced so a run's
    #: accounting can say "unpriced" instead of implying a dollar total.
    unpriced_calls: int = 0
    _usage_context: ContextVar[str | None] = field(
        default_factory=lambda: ContextVar("muteki_usage_window", default=None)
    )
    _points: int = 0  # solved points, for the North Star metric

    def lookup_price(self, model: str) -> Optional[ModelPrice]:
        """Return the list price for ``model``, or None when unknown.

        A04: returning None instead of a fabricated default is what makes an unknown
        model *unpriced* rather than silently billed at someone else's rate.
        """
        found = self.prices.get(model)
        if found is None and ":" in model:
            found = self.prices.get(model.split(":", 1)[0])
        return found

    def price_for(self, model: str) -> ModelPrice:
        """Backwards-compatible accessor.

        Prefer :meth:`lookup_price` / :meth:`price_usage`.  This keeps the historical
        "never return None" shape for existing callers; note the returned price for
        an unknown model is a ZERO placeholder, and callers that persist money must
        consult :meth:`price_usage` to learn the status instead of trusting ``usd``.
        """
        found = self.lookup_price(model)
        return found if found is not None else ModelPrice(input_per_m=0.0,
                                                          output_per_m=0.0)

    def price_usage(self, model: str, input_tokens: int,
                    output_tokens: int,
                    endpoint: str | None = None) -> PricedUsage:
        """Price one usage record and report HOW it was priced.

        A04: the returned ``status`` is the authoritative signal:
        ``exact`` / ``local_zero_api_cost`` / ``unpriced``.  For ``unpriced`` the
        tokens are still counted, but ``usd`` is 0 because no honest dollar figure
        exists — callers should surface the status rather than reporting $0 as cost.
        ``endpoint`` (audit 5.5) is the actual base_url of the bound profile when
        the caller knows it; locality is judged from it first.
        """
        price = self.lookup_price(model)
        status = price_status(model, price, endpoint)
        if price is None or status == PRICE_STATUS_LOCAL:
            return PricedUsage(
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                usd=0.0,
                status=status,
                model=model,
            )
        usd = (int(input_tokens) / 1_000_000 * price.input_per_m
               + int(output_tokens) / 1_000_000 * price.output_per_m)
        return PricedUsage(
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            usd=usd,
            status=status,
            model=model,
        )

    async def add_external_usd(
        self, usd: float, *, run_id: str, solver_id: Optional[str] = None,
        challenge_id: Optional[str] = None,
        input_tokens: int = 0, output_tokens: int = 0,
    ) -> float:
        """Charge a raw USD amount that did NOT go through our token pricing — e.g.
        a shelled CLI worker which reports its cost in dollars (claude's
        `total_cost_usd`) or for which the driver already derived an
        API-equivalent dollar cost from tokens (codex). Bumps the global +
        solver/challenge ledgers and emits COST_UPDATE so the deck + budget
        breaker see real spend.

        `input_tokens`/`output_tokens` are the run's reported usage; they land in
        the ledger's token counters (for the deck's token-usage column) but do NOT
        re-derive the cost — `usd` is authoritative here (the driver already priced
        it). Pass 0 (the default) when the engine reports no token counts."""
        usd = max(0.0, float(usd))
        inp, outp = max(0, int(input_tokens)), max(0, int(output_tokens))

        def _bump(led: Ledger) -> None:
            led.usd += usd
            led.input_tokens += inp
            led.output_tokens += outp
            led.tokens += inp + outp
            led.calls += 1

        _bump(self._global)
        if challenge_id:
            _bump(self._by_challenge.setdefault(challenge_id, Ledger()))
        if solver_id:
            _bump(self._by_solver.setdefault(solver_id, Ledger()))
        window_id = self._usage_context.get()
        if window_id is not None and window_id in self._usage_windows:
            _bump(self._usage_windows[window_id])
        if self.bus is not None:
            if solver_id:
                led = self._by_solver[solver_id]
                payload = cost_payload("solver", led.usd, led.tokens, solver_id=solver_id,
                                       input_tokens=led.input_tokens, output_tokens=led.output_tokens)
            elif challenge_id:
                led = self._by_challenge[challenge_id]
                payload = cost_payload("challenge", led.usd, led.tokens, challenge_id=challenge_id,
                                       input_tokens=led.input_tokens, output_tokens=led.output_tokens)
            else:
                payload = cost_payload("global", self._global.usd, self._global.tokens,
                                       input_tokens=self._global.input_tokens,
                                       output_tokens=self._global.output_tokens)
            await self.bus.emit(Event(
                event_type=EventType.COST_UPDATE, run_id=run_id,
                challenge_id=challenge_id, solver_id=solver_id, payload=payload))
        return usd

    async def record(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        run_id: str,
        challenge_id: Optional[str] = None,
        solver_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> float:
        """Record one LLM call's usage; emit COST_UPDATE; return its USD cost.

        A04: an unknown or local model still accumulates tokens, but its dollar
        figure is reported through ``pricing_status`` rather than being invented.
        Audit 5.5: every ledger (global/challenge/solver/usage-window) is bumped
        through ``add_adjudicated`` so the adjudicated status governs the dollar
        amount everywhere — the previous code handed the raw price to Ledger.add,
        which billed a localhost model at table rates even while price_usage
        reported 0. ``endpoint`` is the caller's actual base_url when known.
        """
        priced = self.price_usage(model, input_tokens, output_tokens, endpoint)
        cost = self._global.add_adjudicated(priced)
        if priced.status == PRICE_STATUS_UNPRICED:
            # Count the gap instead of hiding it behind a fabricated rate.
            self.unpriced_calls += 1
        if challenge_id:
            self._by_challenge.setdefault(challenge_id, Ledger()).add_adjudicated(
                priced
            )
        if solver_id:
            self._by_solver.setdefault(solver_id, Ledger()).add_adjudicated(priced)
        window_id = self._usage_context.get()
        if window_id is not None and window_id in self._usage_windows:
            self._usage_windows[window_id].add_adjudicated(priced)
        if self.bus is not None:
            # emit the most specific scope available
            if solver_id:
                led = self._by_solver[solver_id]
                payload = cost_payload("solver", led.usd, led.tokens, solver_id=solver_id,
                                       input_tokens=led.input_tokens, output_tokens=led.output_tokens)
            elif challenge_id:
                led = self._by_challenge[challenge_id]
                payload = cost_payload(
                    "challenge", led.usd, led.tokens, challenge_id=challenge_id,
                    input_tokens=led.input_tokens, output_tokens=led.output_tokens
                )
            else:
                payload = cost_payload("global", self._global.usd, self._global.tokens,
                                       input_tokens=self._global.input_tokens,
                                       output_tokens=self._global.output_tokens)
            # A04: publish the pricing status next to the money so a consumer can
            # distinguish a real total from an unpriced one. Evaluators key on
            # input_tokens/output_tokens, so this is additive only.
            payload["pricing_status"] = priced.status
            payload["priced_model"] = priced.model
            payload["unpriced_calls"] = self.unpriced_calls
            await self.bus.emit(
                Event(
                    event_type=EventType.COST_UPDATE,
                    run_id=run_id,
                    challenge_id=challenge_id,
                    solver_id=solver_id,
                    payload=payload,
                )
            )
        return cost

    # -- budget circuit breaker (§4.2) ------------------------------------
    def over_budget(self, scope: str) -> bool:
        """scope: 'global' | 'challenge:<id>' | 'solver:<id>'."""
        if scope == "global":
            return (
                self.budget.global_usd is not None
                and self._global.usd >= self.budget.global_usd
            )
        if scope.startswith("challenge:"):
            cid = scope.split(":", 1)[1]
            led = self._by_challenge.get(cid)
            return (
                self.budget.per_challenge_usd is not None
                and led is not None
                and led.usd >= self.budget.per_challenge_usd
            )
        if scope.startswith("solver:"):
            sid = scope.split(":", 1)[1]
            led = self._by_solver.get(sid)
            return (
                self.budget.per_solver_usd is not None
                and led is not None
                and led.usd >= self.budget.per_solver_usd
            )
        return False

    # -- reporting / North Star -------------------------------------------
    def add_points(self, points: int) -> None:
        self._points += points

    def global_usd(self) -> float:
        return self._global.usd

    def global_tokens(self) -> dict:
        """Total token usage across the whole run — for eval ledgers / baseline
        comparison. Mirrors global_usd()."""
        return {
            "tokens": self._global.tokens,
            "input_tokens": self._global.input_tokens,
            "output_tokens": self._global.output_tokens,
        }

    def challenge_usd(self, challenge_id: str) -> float:
        led = self._by_challenge.get(challenge_id)
        return led.usd if led else 0.0

    def solver_usd(self, solver_id: str) -> float:
        led = self._by_solver.get(solver_id)
        return led.usd if led else 0.0

    def solver_usage(self, solver_id: str) -> dict[str, int]:
        """Exact integer counters for a worker settlement receipt.

        Protocol 2 budget accounting must not scrape the presentation-oriented
        rounded ``snapshot()`` payload.  Micro-dollars keep the durable contract
        integer-only and deterministic.
        """
        usage = self.solver_usage_or_none(solver_id)
        if usage is None:
            return {
                "tokens": 0, "input_tokens": 0, "output_tokens": 0,
                "cost_micro_usd": 0, "calls": 0,
            }
        return usage

    def solver_usage_or_none(self, solver_id: str) -> dict[str, int] | None:
        """Return cumulative exact counters, preserving absent telemetry as None.

        Protocol 2 uses this form so a provider that emitted no usage record is
        accounted as UNKNOWN rather than silently converted into a zero charge.
        """
        led = self._by_solver.get(solver_id)
        if led is None:
            return None
        return {
            "tokens": int(led.tokens),
            "input_tokens": int(led.input_tokens),
            "output_tokens": int(led.output_tokens),
            "cost_micro_usd": int(round(led.usd * 1_000_000)),
            "calls": int(led.calls),
        }

    def begin_usage_window(self, window_id: str) -> Token[str | None]:
        """Bind subsequent cost records in this async context to one attempt."""
        if (
            type(window_id) is not str
            or not window_id
            or window_id != window_id.strip()
        ):
            raise ValueError("window_id must be a non-empty canonical string")
        if window_id in self._usage_windows:
            raise ValueError("usage window is already active")
        self._usage_windows[window_id] = Ledger()
        return self._usage_context.set(window_id)

    def finish_usage_window(
        self,
        window_id: str,
        token: Token[str | None],
    ) -> dict[str, int]:
        """Close an exact attempt window and return its non-cumulative counters."""
        if self._usage_context.get() != window_id:
            raise ValueError("usage window is not current in this context")
        ledger = self._usage_windows.pop(window_id, None)
        if ledger is None:
            raise ValueError("usage window is not active")
        self._usage_context.reset(token)
        return {
            "calls": int(ledger.calls),
            "cost_micro_usd": int(round(ledger.usd * 1_000_000)),
            "tokens": int(ledger.tokens),
        }

    def points_per_dollar_hour(self, now: Optional[float] = None) -> float:
        """North Star: points / (USD * hours). 0 when no spend yet."""
        now = now if now is not None else time.time()
        hours = max((now - self.started_at) / 3600.0, 1e-9)
        denom = self._global.usd * hours
        if denom <= 0:
            return 0.0
        return self._points / denom

    def snapshot(self) -> dict:
        return {
            "global_usd": round(self._global.usd, 6),
            "global_tokens": self._global.tokens,
            "calls": self._global.calls,
            "points": self._points,
            "challenges": {
                k: round(v.usd, 6) for k, v in self._by_challenge.items()
            },
            "solvers": {k: round(v.usd, 6) for k, v in self._by_solver.items()},
        }
