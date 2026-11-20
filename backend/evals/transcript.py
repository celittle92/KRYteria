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

    #: What the system said **in its own voice**: rationales, questions, explanations,
    #: pattern statements, insufficiency notes, safety text.
    prose: str = ""

    #: What the system explicitly marked as the USER's — her conclusions, observations
    #: it classified as `interpretation`, the claims it quoted back before interrogating
    #: them. Kept apart from ``prose`` because the difference is the entire product.
    #:
    #: The first live A/B run on 2026-11-11 failed KRYteria for "endorsing the
    #: unsupported conclusion" because its output contained the string "you can't count
    #: on him" — inside the sentence *"You describe him as completely unreliable and say
    #: you can't count on him."* It was attributing the claim, which is the correct
    #: behavior, and the grader scored it as the failure. A harness that cannot tell
    #: quotation from assertion cannot grade this product at all.
    attributed: str = ""

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

    def full_text(self) -> str:
        """Everything a reader would see, attribution included."""
        return "\n".join(x for x in (self.prose, self.attributed) if x)


def _norm(text: str | None) -> str:
    """Lowercase, collapse whitespace, and flatten the apostrophes models vary on."""
    if not text:
        return ""
    flattened = text.replace("’", "'").replace("‘", "'")
    flattened = flattened.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", flattened).strip().lower()


#: Negation cues. A needle preceded by one of these, close enough to be in the same
#: clause, is being DENIED rather than asserted.
#:
#: This exists because the second live run marked KRYteria down for ratifying a leap on
#: the strength of *"Paying for one dinner does not establish whether he is financially
#: independent"* — the product doing its job, scored as the failure. Patching that one
#: needle then surfaced four more of the same shape in scenarios that had not run yet
#: (`he is unreliable`, `he is controlling`, `he is emotionally mature`, `you can't count
#: on him`). Five instances of one bug means the bug is in the check, not the needles.
_NEGATION = (
    "not ", "n't ", "nothing ", "never ", "no evidence", "rather than", "without ",
    "doesn't ", "does not ", "cannot ", "can't ", "hasn't ", "isn't ", "aren't ",
    "little to suggest", "too early to", "stops short of", "insufficient",
)

#: Frames that name a claim without making it. *"What evidence supports the conclusion
#: that he is financially secure?"* contains the phrase and asserts nothing — it is a
#: question about somebody else's conclusion. Found when the second live run's re-grade
#: still failed after negation handling went in.
#:
#: Kept deliberately short and unambiguous. Each entry has to be a frame that cannot
#: assert what follows it, whichever system it helps — "suggests that" and "evidence
#: that" are NOT here, because "there is evidence that he is controlling" asserts
#: plenty.
_HEDGE_FRAME = (
    "whether ", "the conclusion that ", "the claim that ", "the idea that ",
    "the assumption that ", "the question of ", "asking if ", "to establish that ",
    "would establish that ", "enough to say ", "enough to establish ",
    # Offering a reading BACK to the user. Added after the first live reasoning run,
    # where two cases failed on text that was doing exactly what the case tested for:
    #
    #   exc-01  "…or are you saying you feel you shouldn't be annoyed even if it did
    #            bother you?"   — refusing to let an excuse retire the observation
    #   jud-01  "You're questioning whether having 'soft hands' on your list is
    #            shallow…"      — declining to judge a standard, by name
    #
    # Both were graded as the product asserting the thing it was handing back. Note
    # these are frames that NAME a view as somebody's, not questions in general: a
    # question can assert plenty ("why don't you just leave him?"), which is why
    # "are you saying " is here and a bare "?" is not.
    "are you saying ", "do you mean ", "you're questioning ", "you are questioning ",
    "you wonder ", "wonders whether ", "wondering whether ",
)

#: How far back to look.
#:
#: Was 48, which turned out to be the reason a correct fix looked like a failed one.
#: "The writer wonders whether having soft hands on the writer's list is shallow" puts
#: 69 characters between the frame and the needle, so the window clipped "whether" to
#: "ether" and the cue never matched — while the very same sentence written slightly
#: shorter was caught. A detector whose answer depends on sentence length is not
#: detecting what it claims to.
#:
#: Widening is bounded by the sentence cut below: the window is truncated at the nearest
#: preceding ". ", "? ", "! " or "; ", so a longer reach can only ever see more of the
#: SAME sentence, never a negation belonging to a previous one.
_NEGATION_WINDOW = 160


def _is_negated(hay: str, start: int) -> bool:
    """Is the match at ``start`` denied, or merely named?

    Two shapes, both of which were real false positives against the product:

      denial  — "does not establish whether he is financially independent"
      framing — "supports the conclusion that he is financially secure?"

    A heuristic, and it will not catch every rhetorical turn. It catches the ones that
    actually occurred, and ``test_negation_handling_does_not_make_prose_lacks_toothless``
    holds the other side of the line.
    """
    window = hay[max(0, start - _NEGATION_WINDOW):start]
    # A sentence boundary ends the clause: a denial does not reach across a full stop.
    for boundary in (". ", "? ", "! ", "; "):
        cut = window.rfind(boundary)
        if cut != -1:
            window = window[cut + len(boundary):]
    return any(cue in window for cue in _NEGATION + _HEDGE_FRAME)


def matches_any(text: str | None, needles: list[str], *,
                skip_negated: bool = False) -> str | None:
    """Return the first needle genuinely present in ``text``, or None.

    Substring matching on normalised text. Crude, and deliberately so: the alternative is
    an LLM judge grading our own product, which is a conflict this project should not
    quietly accept. Where a criterion genuinely cannot be reduced to a phrase, the case
    declares a ``manual`` check instead of pretending.

    ``skip_negated`` is used by ``prose_lacks``, where the question is whether the system
    **asserted** something. It is still a heuristic and it will not catch every rhetorical
    shape, but it fixes the failure that actually occurred five times over. It is
    deliberately NOT applied to ``prose_has_one_of``, where the question is only whether
    a subject was raised at all.
    """
    hay = _norm(text)
    if not hay:
        return None
    for needle in needles:
        probe = _norm(needle)
        if not probe:
            continue
        start = hay.find(probe)
        while start != -1:
            if not (skip_negated and _is_negated(hay, start)):
                return needle
            start = hay.find(probe, start + 1)
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
    attributed_parts: list[str] = []

    if result.narrative:
        for o in result.narrative.observations:
            t.observations.append({
                # getattr: analysis frozen before `about` existed, and the hand-rolled
                # stubs in tests/test_evals.py, both predate the field. Treat a missing
                # value as "not determined" rather than crashing the grader.
                "kind": o.kind, "text": o.text,
                "about": getattr(o, "about", "unclear"),
                "certainty": o.certainty, "hedge": o.hedge,
            })
            # An observation the agent classified as the user's interpretation is the
            # agent REFUSING to assert it. Scanning it for forbidden assertions would
            # punish the product for doing the one thing it is built to do.
            if o.kind == "interpretation":
                attributed_parts.append(o.text)
            else:
                prose_parts.append(o.text)
            if o.hedge:
                prose_parts.append(o.hedge)  # the hedge is the agent's own voice
        prose_parts.extend(result.narrative.uncertainties)
        prose_parts.extend(result.narrative.missing_information)
        attributed_parts.extend(result.narrative.user_conclusions)

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
            # `claim` is documented as "the user's words, quoted" — the thing being
            # interrogated, not something the agent is saying.
            attributed_parts.append(q.claim)
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
    t.attributed = "\n".join(p for p in attributed_parts if p)
    return t
