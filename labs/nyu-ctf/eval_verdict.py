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

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

#: Batch-5A: bumped whenever acceptance/evidence semantics change, so archived
#: and freshly-produced verdict rows are never compared across semantics.
#: Batch-6A: per-flag temporal binding + artifact generation uncertainty +
#: traversal-proof artifact reads + raw-bytes hashing -> version 4.
VERDICT_VERSION = 4

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
            "verdict_version": VERDICT_VERSION,
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


def _artifact_id(payload: dict[str, Any]) -> str:
    """Artifact reference from a tool.result: top-level or nested in result.

    Batch-5A: the D02 spill originally published the id inside the result view;
    batch-4-3 moved it to the event top level. Accept both so pre/post streams
    replay under one evaluator.
    """
    ref = str(payload.get("artifact_id") or "").strip()
    if ref:
        return ref
    result = payload.get("result")
    if isinstance(result, dict):
        return str(result.get("artifact_id") or "").strip()
    return ""


def _read_artifact(artifacts_dir: Path | None,
                   artifact_id: str) -> tuple[str | None, str]:
    """Read one referenced artifact. Returns (content, sha256); (None, "") when
    the file is absent/unreadable — a missing referenced file is recorded, not
    treated as evidence.

    Batch-6A hardening:
      * artifact_id must be a bare safe filename — traversal (``..``), path
        separators and absolute/UNC forms are rejected outright;
      * the resolved file must remain inside artifacts_dir (symlink escape
        included);
      * sha256 is computed over the RAW file bytes — never over
        newline-normalised text (batch-5 regression: the evaluator reported a
        hash of read_text() output instead of the artifact bytes)."""
    if not artifacts_dir or not artifact_id:
        return None, ""
    ref = artifact_id.replace("\\", "/")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,128}", ref):
        # traversal / separators / dotfiles / absolute forms are rejected
        return None, ""
    base = Path(artifacts_dir).resolve()
    path = (base / f"{ref}.txt").resolve()
    if base != path.parent and base not in path.parents:
        return None, ""
    try:
        raw = path.read_bytes()
    except OSError:
        alt = (base / ref).resolve()
        if base != alt.parent and base not in alt.parents:
            return None, ""
        try:
            raw = alt.read_bytes()
        except OSError:
            return None, ""
    sha = hashlib.sha256(raw).hexdigest()
    content = raw.decode("utf-8", errors="replace")
    return content, sha


def evaluate_attempt(
    events: Iterable[dict[str, Any]],
    *,
    expected_flags: str | Iterable[str],
    attempt: int | None = None,
    accepted_flags: Iterable[str] | None = None,
    artifacts_dir: str | Path | None = None,
) -> Verdict:
    """Decide whether an attempt genuinely solved the challenge.

    ``expected_flags``   the official flag(s).  Used ONLY here, for comparison —
                        never fed to the worker.
    ``attempt``          when given, only acceptance evidence carrying this
                        execution/attempt generation is trusted.
    ``accepted_flags``   externally confirmed flags, if an external judge ran.
    ``artifacts_dir``    workspace/arts of the run (batch-5A): when a
                        tool.result references an artifact whose inline
                        (condensed) text was truncated, the referenced file is
                        read to recover the full output — evidence links then
                        point at the artifact with its SHA-256. Directory
                        scans are NOT evidence: only artifacts referenced by
                        an event count.
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
    #: (seq, OUTPUT-ONLY text, generation, artifact_id) for
    #: acceptance→output traceability. Command text is deliberately excluded:
    #: a flag typed into a command (e.g. submit-flag 'CTF2{…}') is worker
    #: input, not target response.
    tool_outputs: list[tuple[int, str, int | None, str]] = []

    for event in events:
        etype = str(event.get("event_type") or "")
        payload = event.get("payload") or {}
        blob = json.dumps(event, ensure_ascii=False)

        if etype in {"tool.result", "tool_result"}:
            tool_outputs.append((
                _event_seq(event), _output_text(payload),
                _event_generation(payload), _artifact_id(payload)))
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
    acceptance_rows: list[tuple[str, int, dict[str, Any], int | None, str]] = []
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

        acceptance_rows.append((etype, _event_seq(event), payload, gen,
                                structured))
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
    # A flag.accepted event alone proves a decision, not an execution. The flag
    # value must trace to a tool.result OUTPUT with:
    #   * inline evidence — the flag inside the whitelist output fields, OR
    #   * artifact evidence — the event references an artifact whose FILE
    #     content contains the flag (batch-5A: condensed output is truncated
    #     head-600; the tail lives in workspace/arts/<id>.txt).
    # Temporal association (batch-5A): the output must precede the acceptance
    # event — an output appearing only AFTER the terminal event cannot be the
    # source of that acceptance. Directory scans are not evidence: only
    # artifacts referenced by an event are read.
    gen_uncertain = False
    if verdict.gate_accepted:
        artifacts_dir_path = Path(artifacts_dir) if artifacts_dir else None
        # Batch-6A: PER-FLAG temporal binding. Each flag's output must precede
        # THAT flag's own earliest acceptance event — using the global earliest
        # acceptance cut off the second flag of a multi-flag solve (its
        # legitimate output lands after flag #1 was accepted).
        bound_by_flag: dict[str, int] = {}
        for _etype, seq, payload, _gen, structured in acceptance_rows:
            text = structured or _output_text(payload)
            for f in flags:
                if f in text:
                    prev = bound_by_flag.get(f)
                    bound_by_flag[f] = seq if prev is None else min(prev, seq)
        for value in dict.fromkeys(accepted_values):
            bound_seq = bound_by_flag.get(value, 0)
            inline_hits: list[int] = []
            missing_refs: list[str] = []
            for seq, text, gen, aid in tool_outputs:
                if seq > bound_seq:
                    continue
                if _mentions(text, value):
                    inline_hits.append(seq)
                    if attempt is not None and gen is None:
                        gen_uncertain = True
                elif aid:
                    content, sha = _read_artifact(artifacts_dir_path, aid)
                    if content is None:
                        missing_refs.append(aid)
                    elif _mentions(content, value):
                        verdict.evidence_links.append({
                            "flag": value, "event_type": "artifact",
                            "seqs": [seq], "artifact_id": aid,
                            "sha256": sha})
                        # Batch-6A: generation uncertainty propagates through
                        # the artifact branch too (previously inline-only).
                        if attempt is not None and gen is None:
                            gen_uncertain = True
                        break
            if inline_hits:
                verdict.evidence_links.append({
                    "flag": value, "event_type": "tool.result",
                    "seqs": sorted(inline_hits)[:5]})
                continue
            artifact_hit = any(
                l.get("flag") == value
                and l.get("event_type") == "artifact"
                for l in verdict.evidence_links)
            if artifact_hit:
                continue
            verdict.unlinked_flags.append(value)
            if missing_refs:
                verdict.evidence_links.append({
                    "flag": value, "event_type": "missing_artifact",
                    "artifact_ids": sorted(set(missing_refs))[:5]})
        if verdict.unlinked_flags:
            verdict.gate_accepted = False
            verdict.reason = (
                "接受事件无法回查到包含 flag 的真实工具输出或其引用的产物: "
                f"{sorted(set(verdict.unlinked_flags))}")

    verdict.attempt_matched = (verdict.gate_accepted
                               or verdict.external_verified) and not gen_uncertain
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
