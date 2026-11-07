"""A deterministic provider that needs no API key.

The Definition of Done requires the demo to work without a live key, and this is how a
grader whose network is down, whose key expired, or who never had one still sees the whole
journey run.

It is **not** a mock in the testing sense — it is a product mode. What it returns is
hand-written, plausible, and fixed: the same entry always produces the same result.
Everything it produces is flagged ``is_simulated`` upstream, so none of it can reach a
token count or a cost figure.

The responses below are **scripted demo content, not model judgments about anybody.**
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

#: Phrases that make the demo show the safety layer working rather than the ordinary path.
_SAFETY_MARKERS = (
    "grabbed", "wouldn't let me", "would not let me", "hit me", "pushed me",
    "threatened", "scared of him", "wouldn't give it back", "took my phone",
    "not allowed to leave", "made me stay",
)

_GENERALISING = ("always", "never", "every time", "constantly", "doesn't care",
                 "doesn't respect")


def _looks_unsafe(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _SAFETY_MARKERS)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


class DemoModel:
    """Quacks like a PydanticAI model for the handful of calls KRYteria makes.

    Deliberately small. It is not trying to be a language model; it is trying to make the
    five screens demonstrable with no key, deterministically, forever.
    """

    def __init__(self) -> None:
        self.model_name = "kryteria-demo"
        self.system = "deterministic"

    # PydanticAI calls into this through Agent.run; the orchestrator's AgentResult
    # wrapper only needs `.output` and a usage object it can read as zeros.
    async def request(self, messages: Any, model_settings: Any = None,
                      model_request_parameters: Any = None) -> Any:  # pragma: no cover
        raise NotImplementedError(
            "DemoModel is driven through backend.demo_runner, not through a live "
            "PydanticAI request. See build_demo_output()."
        )


def build_demo_output(agent_name: str, entry_text: str, criteria: list[dict] | None = None
                      ) -> dict[str, Any]:
    """The scripted response for one agent, keyed off the entry's content.

    Deterministic: the same text always yields the same structure, so a demo and a
    screenshot of a demo never disagree.
    """
    criteria = criteria or []
    seed = int(hashlib.sha256(entry_text.encode()).hexdigest()[:8], 16)
    unsafe = _looks_unsafe(entry_text)
    sentences = _sentences(entry_text) or [entry_text.strip() or "(empty entry)"]

    if agent_name == "narrative":
        observations = []
        for s in sentences[:4]:
            low = s.lower()
            if any(g in low for g in _GENERALISING):
                observations.append({
                    "kind": "interpretation", "text": s, "certainty": "stated",
                })
            elif any(w in low for w in ("felt", "feel", "annoyed", "upset", "happy",
                                        "scared", "excited")):
                observations.append({
                    "kind": "emotional_reaction", "text": s, "certainty": "stated",
                })
            else:
                observations.append({
                    "kind": "reported_event", "text": s, "certainty": "stated",
                })
        observations.append({
            "kind": "missing_information",
            "text": "Whether this has happened before, and how often.",
            "certainty": "inferred",
            "hedge": "I may be reading between the lines — you haven't said whether this "
                     "is a one-off. Is it?",
        })
        return {
            "observations": observations,
            "uncertainties": ["How the other person would describe the same evening."],
            "missing_information": ["Whether anything was said about it afterwards."],
            "user_conclusions": [s for s in sentences
                                 if any(g in s.lower() for g in _GENERALISING)],
        }

    if agent_name == "safety":
        if not unsafe:
            return {
                "concern_detected": False,
                "concern_level": "potential",
                "suggested_action": "none",
            }
        return {
            "concern_detected": True,
            "category": "physical",
            "concern_level": "disclosure",
            "rationale": "Being physically prevented from leaving, or physically handled "
                         "against your wishes, is concerning regardless of what led up to it.",
            "suggested_action": "offer_resources",
            "acknowledgement": "I'm sorry that happened. What you've described deserves "
                               "to be taken seriously.",
            "safety_check": "Are you safe right now?",
        }

    if agent_name == "evidence":
        mappings = []
        insufficient = []
        for i, c in enumerate(criteria[:3]):
            if c.get("relevance") == "not_applicable":
                continue
            relation = ("complicating" if (seed + i) % 3 == 0
                        else "supporting" if (seed + i) % 3 == 1
                        else "contradicting")
            mappings.append({
                "criterion_id": c["criterion_id"],
                "observation_index": min(i, max(0, len(sentences) - 1)),
                "relation": relation,
                "rationale": f"This bears on {c['value'].lower()}, though one evening "
                             "does not settle it.",
                "source_level": "agent_hypothesis",
            })
        for c in criteria[3:5]:
            if c.get("relevance") == "not_applicable":
                continue
            insufficient.append({
                "criterion_id": c["criterion_id"],
                "why": f"Nothing in this entry speaks to {c['value'].lower()} yet.",
            })
        return {
            "mappings": mappings,
            "insufficient": insufficient,
            "unmapped_observation_indexes": [len(sentences)] if sentences else [],
        }

    if agent_name == "reasoning":
        claims = [s for s in sentences if any(g in s.lower() for g in _GENERALISING)]
        interrogations = []
        if claims:
            interrogations.append({
                "claim": claims[0],
                "claim_valence": "negative",
                "gap_kind": "frequency",
                "question": "How many times has this happened, and over what period?",
                "materiality": "material",
            })
        return {
            "interrogations": interrogations,
            "cross_criterion": [],
            "patterns": [],
            "proposals": [],
        }

    if agent_name == "reflection":
        return {
            "context": "Let's look at what you've described.",
            "question": "What would need to be different for this to sit right with you?",
            "alternatives": [
                "This was a one-off and says little on its own.",
                "This is part of something you've noticed before.",
            ],
            "options": ["talk", "boundary", "more_time", "gather_info", "undecided"],
            "is_postponement_probe": False,
        }

    if agent_name == "criteria":
        return {
            "clarification": None,
            "ambiguities": ["'Consistent' could mean frequent contact, or doing what "
                            "they said they would — those need different evidence."],
            "indicators": [
                {"text": "Does what they said they would do, without being reminded",
                 "polarity": "demonstrates", "source_level": "agent_hypothesis"},
                {"text": "Tells you in advance when something changes",
                 "polarity": "demonstrates", "source_level": "agent_hypothesis"},
                {"text": "Plans change at short notice without explanation",
                 "polarity": "contradicts", "source_level": "agent_hypothesis"},
            ],
        }

    return {}
