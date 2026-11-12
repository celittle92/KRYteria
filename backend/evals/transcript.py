"""One gradable shape, whatever produced it.

The A/B comparison is the reason this exists. KRYteria returns structured output; a
generic chatbot returns a paragraph. Grading them with two different vocabularies would
make the comparison meaningless — of course the system built to emit structure scores
better on structure. So both are normalised into a ``Transcript``, and every check runs
against that.

What the normalisation deliberately preserves is the asymmetry itself. A chatbot
transcript has ``structured=False`` and empty lists, and a check that needs structure
returns **not_applicable** rather than ``fail``. The report then states plainly that the
baseline could not be graded on that dimension *because it does not produce the
information*. That is a finding about the comparison, not a point scored off it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: Criterion ids are what the agents work in; the eval cases are written in names, which
#: is how a person would state the requirement. Everything below is resolved to names.
CriterionNames = dict[int, str]


@dataclass
class Transcript:
    """What one system produced for one case, flattened for grading."""

    system: str
    prose: str = ""
    structured: bool = True

    observations: list[dict] = field(default_factory=list)
    mappings: list[dict] = field(default_factory=list)
    insufficient: list[dict] = field(default_factory=list)
    interrogations: list[dict] = field(default_factory=list)
    patterns: list[dict] = field(default_factory=list)
    proposals: list[dict] = field(default_factory=list)
    cross_criterion: list[dict] = field(default_factory=list)

    safety: dict | None = None
    safety_events: list[dict] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)
    halted: bool = False

    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    simulated: bool = True
    errors: list[str] = field(default_factory=list)

    def normalised_prose(self) -> str:
        return _norm(self.prose)


def _norm(text: str | None) -> str:
    """Lowercase, collapse whitespace, and flatten the apostrophes models vary on."""
    if not text:
        return ""
    flattened = text.replace("’", "'").replace("‘", "'")
    flattened = flattened.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", flattened).strip().lower()


def matches_any(text: str | None, needles: list[str]) -> str | None:
    """Return the first needle present in ``text``, or None.

    Substring matching on normalised text. Crude, and deliberately so: the alternative is
    an LLM judge grading our own product, which is a conflict this project should not
    quietly accept. Where a criterion genuinely cannot be reduced to a phrase, the case
    declares a ``manual`` check instead of pretending.
    """
    hay = _norm(text)
    if not hay:
        return None
    for needle in needles:
        if _norm(needle) in hay:
            return needle
    return None


def from_prose(system: str, prose: str, *, model_calls: int = 1,
               input_tokens: int = 0, output_tokens: int = 0, latency_ms: int = 0,
               simulated: bool = True, errors: list[str] | None = None) -> Transcript:
    """A baseline chatbot's reply: words, and nothing else to inspect."""
    return Transcript(
        system=system, prose=prose, structured=False,
        model_calls=model_calls, input_tokens=input_tokens,
        output_tokens=output_tokens, latency_ms=latency_ms,
        simulated=simulated, errors=list(errors or []),
    )


def from_brain_dump(result: Any, names: CriterionNames,
                    safety_events: list[dict] | None = None) -> Transcript:
    """Flatten a ``BrainDumpResult`` into the common shape."""
    t = Transcript(system="kryteria", structured=True)

    t.model_calls = result.model_calls
    t.input_tokens = result.input_tokens
    t.output_tokens = result.output_tokens
    t.latency_ms = sum(s.latency_ms for s in result.steps)
    t.simulated = all(s.simulated for s in result.steps) if result.steps else True
    t.errors = list(result.errors)
    t.halted = bool(result.halted)
    t.resources = list(result.resources or [])
    t.safety_events = list(safety_events or [])

    prose_parts: list[str] = []

    if result.narrative:
        for o in result.narrative.observations:
            t.observations.append({
                "kind": o.kind, "text": o.text,
                "certainty": o.certainty, "hedge": o.hedge,
            })
            prose_parts.append(o.text)
            if o.hedge:
                prose_parts.append(o.hedge)
        prose_parts.extend(result.narrative.uncertainties)
        prose_parts.extend(result.narrative.missing_information)
        prose_parts.extend(result.narrative.user_conclusions)

    if result.safety:
        s = result.safety
        t.safety = {
            "concern_detected": s.concern_detected,
            "category": s.category,
            "concern_level": s.concern_level,
            "suggested_action": s.suggested_action,
            "safety_check": s.safety_check,
            "acknowledgement": s.acknowledgement,
            "rationale": s.rationale,
        }
        prose_parts.extend(x for x in (s.acknowledgement, s.safety_check, s.rationale) if x)

    if result.evidence:
        for m in result.evidence.mappings:
            t.mappings.append({
                "criterion_id": m.criterion_id,
                "criterion": names.get(m.criterion_id, f"#{m.criterion_id}"),
                "relation": m.relation,
                "source_level": m.source_level,
                "research_ref": m.research_ref,
                "rationale": m.rationale,
            })
            if m.rationale:
                prose_parts.append(m.rationale)
        for n in result.evidence.insufficient:
            t.insufficient.append({
                "criterion_id": n.criterion_id,
                "criterion": names.get(n.criterion_id, f"#{n.criterion_id}"),
                "why": n.why,
            })
            prose_parts.append(n.why)

    if result.reasoning:
        for q in result.reasoning.interrogations:
            t.interrogations.append({
                "claim": q.claim, "claim_valence": q.claim_valence,
                "gap_kind": q.gap_kind, "question": q.question,
                "materiality": q.materiality,
            })
            prose_parts.append(q.question)
        for c in result.reasoning.cross_criterion:
            t.cross_criterion.append({
                "criterion_ids": list(c.criterion_ids),
                "criteria": [names.get(i, f"#{i}") for i in c.criterion_ids],
                "explanation": c.explanation,
                "competing": c.competing,
            })
            prose_parts.append(c.explanation)
        for p in result.reasoning.patterns:
            t.patterns.append({
                "kind": p.kind, "statement": p.statement,
                "criterion_id": p.criterion_id,
                "criterion": names.get(p.criterion_id) if p.criterion_id else None,
                "supporting_entry_ids": list(p.supporting_entry_ids),
                "contradicting_entry_ids": list(p.contradicting_entry_ids),
                "evidence_strength": p.evidence_strength,
                "alternatives": list(p.alternatives),
                "uncertainties": list(p.uncertainties),
                "gap_note": p.gap_note,
            })
            prose_parts.append(p.statement)
        for pr in result.reasoning.proposals:
            t.proposals.append({
                "criterion_id": pr.criterion_id,
                "criterion": names.get(pr.criterion_id, f"#{pr.criterion_id}"),
                "proposed_status": pr.proposed_status,
                "rationale": pr.rationale,
            })
            prose_parts.append(pr.rationale)

    if result.reflection:
        r = result.reflection
        prose_parts.append(r.question)
        if r.context:
            prose_parts.append(r.context)
        prose_parts.extend(r.alternatives)

    t.prose = "\n".join(p for p in prose_parts if p)
    return t
