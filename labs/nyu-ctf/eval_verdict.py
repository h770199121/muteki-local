"""A02 — a solved verdict must trace back to a real accepted execution.

The evaluation harness decided success with::

    flag_found = ch["flag"] in json.dumps(events)

Any occurrence of the flag string anywhere in the event stream counted as solved —
including the challenge description, an operator hint, or a model guess.  A
synthetic stream containing only ``text.delta`` and no tool execution at all still
evaluated True.

This module replaces that with an evidence-based verdict that separates three
distinct facts:

``candidate_found``   the flag string appeared somewhere (weakest — text only)
``gate_accepted``     muteki's own Flag gate accepted it (tool execution + verdict)
``external_verified`` an external judge confirmed it

``solved`` is true only when the acceptance evidence belongs to the CURRENT attempt
and traces back to a real tool output or artifact.  A rejected candidate never
counts, no matter how it was produced.

Dependency-free by design: the project venv cannot import pydantic.

Run:  python -X utf8 -B -m unittest tests.test_eval_verdict -v
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

# Event types that indicate the worker actually executed something.
EXECUTION_EVENT_TYPES = frozenset({
    "tool.start", "tool_start",
    "tool.result", "tool_result", "tool.end", "tool_end",
    "blackboard.delta",
})

# Event types that record a trusted terminal/acceptance decision.
ACCEPT_EVENT_TYPES = frozenset({
    "flag.accepted", "flag_accepted",
    "run.finished", "run_finished",
    "submit.ok", "submit_ok",
})

# Event types that explicitly REJECT a candidate.
REJECT_HINTS = ("rejected", "denied", "invalid", "incorrect", "wrong", "mismatch")

# Text-only event types: these can quote the challenge or a hint, so a bare
# occurrence of the flag string here is a candidate, never a proof.
TEXT_ONLY_EVENT_TYPES = frozenset({
    "text.delta", "text_delta", "assistant.text", "message.delta",
    "run.started", "run_started", "worker.finished", "worker_finished",
})


@dataclass
class Verdict:
    """Evidence-based evaluation result for a single attempt."""

    candidate_found: bool = False
    gate_accepted: bool = False
    external_verified: bool = False
    solved: bool = False

    #: where the candidate text was seen ("text.delta:12", "tool.result:88", ...)
    candidate_sources: list[str] = field(default_factory=list)
    #: event seq numbers backing the acceptance
    acceptance_sources: list[str] = field(default_factory=list)

    #: True when acceptance evidence belongs to this attempt
    attempt_matched: bool = False
    #: True when at least one executed tool output was observed
    execution_observed: bool = False
    rejected_candidates: int = 0
    multi_flag_satisfied: dict[str, bool] = field(default_factory=dict)
    #: audit 5.3 follow-up: for each gate-accepted flag, the tool.result events
    #: that actually contain the flag value — the traceable real-output source.
    evidence_links: list[dict[str, Any]] = field(default_factory=list)
    #: accepted flag values that could NOT be traced to any tool output
    unlinked_flags: list[str] = field(default_factory=list)

    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "solved": self.solved,
            "candidate_found": self.candidate_found,
            "gate_accepted": self.gate_accepted,
            "external_verified": self.external_verified,
            "candidate_sources": sorted(set(self.candidate_sources)),
            "acceptance_sources": sorted(set(self.acceptance_sources)),
            "attempt_matched": self.attempt_matched,
            "execution_observed": self.execution_observed,
            "rejected_candidates": self.rejected_candidates,
            "multi_flag_satisfied": self.multi_flag_satisfied,
            "evidence_links": self.evidence_links,
            "unlinked_flags": sorted(set(self.unlinked_flags)),
            "reason": self.reason,
        }


def _event_seq(event: dict[str, Any]) -> int:
    try:
        return int(event.get("seq") or 0)
    except (TypeError, ValueError):
        return 0


def _is_rejection(payload: dict[str, Any]) -> bool:
    for key in ("status", "verdict", "result", "decision", "accepted"):
        value = str(payload.get(key) or "").lower()
        if value and any(hint in value for hint in REJECT_HINTS):
            return True
    return bool(payload.get("rejected"))


def _mentions(text: str, flag: str) -> bool:
    return bool(flag) and flag in text


def _output_text(payload: dict[str, Any]) -> str:
    """Extract ONLY the output fields of a tool.result payload (audit batch-4-1).

    Matching the whole event JSON let a flag inside the COMMAND text (e.g.
    ``submit-flag 'CTF2{…}'``) count as "real output" — the command is worker
    input, not target response. The whitelist covers the shapes this project
    emits: ``result.condensed`` (dict) / ``result`` (str) / ``output`` /
    ``content``. Everything else (tool name, artifact ids, generations) is
    deliberately excluded.
    """
    parts: list[str] = []
    for key in ("output", "content"):
        value = payload.get(key)
        if isinstance(value, str):
            parts.append(value)
    result = payload.get("result")
    if isinstance(result, Mapping):
        condensed = result.get("condensed")
        if isinstance(condensed, str):
            parts.append(condensed)
    elif isinstance(result, str):
        parts.append(result)
    return "\n".join(parts)


def _event_generation(payload: dict[str, Any]) -> int | None:
    gen = payload.get("execution_generation")
    if gen is None:
        return None
    try:
        return int(gen)
    except (TypeError, ValueError):
        return None


def evaluate_attempt(
    events: Iterable[dict[str, Any]],
    *,
    expected_flags: str | Iterable[str],
    attempt: int | None = None,
    accepted_flags: Iterable[str] | None = None,
) -> Verdict:
    """Decide whether an attempt genuinely solved the challenge.

    ``expected_flags``   the official flag(s).  Used ONLY here, for comparison —
                        never fed to the worker.
    ``attempt``          when given, only acceptance evidence carrying this
                        execution/attempt generation is trusted.
    ``accepted_flags``   externally confirmed flags, if an external judge ran.
    """
    events = list(events)

    if isinstance(expected_flags, str):
        flags = [expected_flags] if expected_flags else []
    else:
        flags = [f for f in expected_flags if f]
    flags = [f for f in flags if f]

    # Gate-derived flags (audit D10 follow-up): when the harness holds no
    # official value (platform instances), the coordinator's RUN_FINISHED flag
    # is the only candidate. It is NOT trusted blindly — it enters the same
    # evidence pipeline and must trace to a real tool output, or the verdict
    # stays unsolved-with-reason and records unlinked_flags.
    gate_derived = False
    if not flags:
        for event in events:
            if str(event.get("event_type") or "") in ACCEPT_EVENT_TYPES:
                payload = event.get("payload") or {}
                if payload.get("solved") is True:
                    value = str(payload.get("flag") or "")
                    if value and value not in flags:
                        flags.append(value)
                        gate_derived = True

    verdict = Verdict()

    if not flags:
        verdict.reason = "没有可比对的官方 flag，无法判定"
        return verdict

    # ---- pass 1: was there any execution at all, and did text merely echo? ----
    exec_seqs: list[int] = []
    text_hits: list[str] = []
    tool_hits: list[str] = []
    #: audit 5.3 follow-up + batch-4-1: REAL tool outputs (tool.result only —
    #: tool.start is the command input, text.delta is prose), as
    #: (seq, OUTPUT-ONLY text, generation) for acceptance→output traceability.
    #: Command text is deliberately excluded: a flag typed into a command (e.g.
    #: submit-flag 'CTF2{…}') is worker input, not target response.
    tool_outputs: list[tuple[int, str, int | None]] = []

    for event in events:
        etype = str(event.get("event_type") or "")
        payload = event.get("payload") or {}
        blob = json.dumps(event, ensure_ascii=False)

        if etype in {"tool.result", "tool_result"}:
            tool_outputs.append((
                _event_seq(event), _output_text(payload),
                _event_generation(payload)))
        if etype in EXECUTION_EVENT_TYPES or etype.startswith("tool."):
            exec_seqs.append(_event_seq(event))

        for flag in flags:
            if not _mentions(blob, flag):
                continue
            label = f"{etype or 'unknown'}:{_event_seq(event)}"
            if etype in TEXT_ONLY_EVENT_TYPES:
                text_hits.append(label)
            else:
                tool_hits.append(label)

    # Batch-4-1 generation binding: when an attempt is specified, outputs from
    # other generations are not evidence for THIS attempt.
    if attempt is not None:
        tool_outputs = [row for row in tool_outputs
                        if row[2] is None or row[2] == int(attempt)]

    verdict.execution_observed = bool(exec_seqs)
    verdict.candidate_sources = text_hits + tool_hits
    verdict.candidate_found = bool(verdict.candidate_sources)

    # ---- pass 2: trusted acceptance, scoped to this attempt ----
    #: batch-4-1: gate acceptance requires EVERY expected flag to carry
    #: acceptance evidence (same "all" semantics as the external judge).
    accepted_values: set[str] = set()
    acceptance_rows: list[tuple[str, int, dict[str, Any], int | None]] = []
    for event in events:
        etype = str(event.get("event_type") or "")
        payload = event.get("payload") or {}

        is_accept_type = etype in ACCEPT_EVENT_TYPES
        if not is_accept_type:
            continue
        if _is_rejection(payload):
            verdict.rejected_candidates += 1
            continue

        # run.finished may only serve as acceptance evidence when the
        # coordinator itself marked the run solved (batch-4-1③): a finished
        # payload carrying a flag string with solved=false is a candidate
        # record, not an acceptance.
        if etype in {"run.finished", "run_finished"} and payload.get("solved") is not True:
            continue

        # Structured flag fields on acceptance events are authoritative; fall
        # back to the OUTPUT-only text for events without structured fields.
        structured = ""
        for key in ("flag", "flags"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                structured += f"\n{value}"
            elif isinstance(value, list):
                structured += "\n" + "\n".join(
                    str(v) for v in value if v)
        mentions = any(
            _mentions(structured or _output_text(payload), f) for f in flags)
        if not mentions:
            continue

        # Scope the acceptance to the attempt when a generation is available.
        gen = _event_generation(payload)
        if attempt is not None and gen is not None and gen != int(attempt):
            continue

        acceptance_rows.append((etype, _event_seq(event), payload, gen))
        verdict.acceptance_sources.append(f"{etype}:{_event_seq(event)}")
        accepted_values.update(f for f in flags
                               if _mentions(structured or _output_text(payload), f))

    verdict.gate_accepted = bool(flags) and all(
        f in accepted_values for f in flags)

    # ---- pass 3: external judge ----
    if accepted_flags is not None:
        external = {f for f in accepted_flags if f}
        # Audit 5.3: multi-flag completion requires EVERY expected flag to be
        # externally confirmed — one confirmed flag of two expected must not
        # score the attempt as solved.
        verdict.external_verified = bool(flags) and all(f in external for f in flags)
        verdict.multi_flag_satisfied = {f: f in external for f in flags}

    # ---- final: acceptance must be backed by real execution ----
    if verdict.gate_accepted and not verdict.execution_observed:
        verdict.gate_accepted = False
        verdict.reason = "接受事件缺少工具执行证据，不予采信"

    # ---- audit 5.3 follow-up: acceptance must trace to REAL tool output ----
    # A flag.accepted event alone proves a decision, not an execution: the same
    # flag value must be findable in at least one tool.result OUTPUT (whitelist
    # fields only — see _output_text). Otherwise the acceptance is downgraded
    # (an operator echo / board write cannot count).
    if verdict.gate_accepted:
        for value in dict.fromkeys(accepted_values):
            hits = [seq for seq, text, _gen in tool_outputs
                    if _mentions(text, value)]
            if hits:
                verdict.evidence_links.append({
                    "flag": value, "event_type": "tool.result",
                    "seqs": sorted(hits)[:5]})
            else:
                verdict.unlinked_flags.append(value)
        if verdict.unlinked_flags:
            verdict.gate_accepted = False
            verdict.reason = (
                "接受事件无法回查到包含 flag 的真实工具输出: "
                f"{sorted(set(verdict.unlinked_flags))}")

    verdict.attempt_matched = verdict.gate_accepted or verdict.external_verified
    verdict.solved = bool(
        (verdict.gate_accepted and verdict.execution_observed)
        or verdict.external_verified
    )

    if verdict.solved:
        verdict.reason = "有真实执行来源且被接受"
    elif verdict.candidate_found and not verdict.execution_observed:
        verdict.reason = "仅在文本中出现，无执行证据（可能是题意/hint/猜测）"
    elif verdict.candidate_found and not verdict.gate_accepted:
        verdict.reason = "出现候选但未被接受"
    elif verdict.rejected_candidates:
        verdict.reason = "候选被拒绝"
    else:
        verdict.reason = "未找到 flag"

    return verdict


__all__ = ["Verdict", "evaluate_attempt"]
