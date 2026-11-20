"""Structured output contracts for every KRYteria agent.

Nothing a model returns reaches the database without passing through one of these. The
validators are not decoration — several of the product's promises are impossible to keep
if a malformed or over-confident model response is persisted verbatim:

  * An inferred observation must carry a hedge, so a reading is never presented as
    something the user said.
  * A confident pattern must offer an alternative explanation, so a finding is never a
    verdict.
  * No agent may emit a numeric score for a person or a relationship, in any field.
  * No agent may propose an assessment status without a rationale.

A model that violates one of these produces a validation error, which the orchestrator
records and surfaces as a recoverable state. It does not get written and silently
believed.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------- shared vocabulary

ObservationKind = Literal[
    "reported_event", "interpretation", "emotional_reaction",
    "missing_information", "uncertainty",
]
Certainty = Literal["stated", "inferred"]
#: Whose conduct an observation describes.
#:
#: Added 2026-11-18 after a test run on a Brain Dump that was mostly about the *writer* —
#: his own unanswered messages, his own unpredictable hours, his own uncertainty about what
#: he was willing to change. Every one of those became a mapping against criteria that
#: describe the other person, and so every rationale ended "…but this does not establish
#: whether she can live with it." Twenty rows of doubt about a woman who, in that entry,
#: had done nothing but say that consistency mattered to her.
#:
#: The pipeline had no way to say "this sentence is about you". Now it does. The rules that
#: use it live in the Evidence, Reasoning and Reflection prompts, because which of these a
#: sentence is cannot be decided by a regular expression.
#:
#: ``unclear`` is the default so that analysis frozen before this field existed still
#: loads. It means "not determined", never "about them".
ObservationSubject = Literal["me", "them", "both", "unclear"]
EvidenceRelation = Literal["supporting", "contradicting", "complicating", "unrelated"]
SourceLevel = Literal[
    "established_research", "research_informed", "agent_hypothesis", "user_stated"
]
AssessmentStatus = Literal["pass", "unknown", "fail", "not_applicable"]
EvidenceStrength = Literal["insufficient", "limited", "moderate", "strong"]
SafetyCategory = Literal[
    "physical", "emotional_psychological", "sexual", "coercive_control",
    "stalking_harassment", "self_harm",
]
ConcernLevel = Literal["potential", "pattern", "disclosure", "immediate_danger"]
GapKind = Literal[
    "frequency", "pattern", "magnitude", "communication", "circumstances",
    "accountability", "impact", "definition", "comparison",
]
DecisionChoice = Literal[
    "talk", "boundary", "more_time", "gather_info", "reconsider",
    "revise_criterion", "undecided",
]

#: Phrases that label a person rather than describe a behavior. KRYteria may say
#: "that behavior may be a form of coercive control"; it may never say "he is an abuser".
_LABELLING = re.compile(
    r"\b(?:he|she|they|his|her|their)\s+(?:is|are|was|were)\s+"
    r"(?:an?\s+)?(?:abuser|narcissist|sociopath|psychopath|toxic|abusive|manipulative)\b"
    r"|\bis\s+(?:definitely|clearly|obviously)\s+(?:an?\s+)?"
    r"(?:abuser|narcissist|toxic|abusive)\b",
    re.IGNORECASE,
)

#: A compatibility percentage or rating by any other name.
_SCORE = re.compile(
    r"\b(?:compatibility|match|relationship|partner)\s*(?:score|rating|percentage|index)\b"
    r"|\b\d{1,3}\s*%\s*(?:compatible|match)\b"
    r"|\b(?:rated?|scored?)\s+(?:him|her|them)\b",
    re.IGNORECASE,
)


def _reject_labelling(value: str | None) -> str | None:
    if value and _LABELLING.search(value):
        raise ValueError(
            "Labels a person rather than describing a behavior. KRYteria may say a "
            "behavior 'may be a form of coercive control'; it may not say someone 'is "
            "an abuser'."
        )
    if value and _SCORE.search(value):
        raise ValueError(
            "Contains a compatibility score. KRYteria has no numeric rating for a person "
            "or a relationship, in any field."
        )
    return value


class _NoScoresNoLabels(BaseModel):
    """Base model applying the two prohibitions to every string field."""

    @model_validator(mode="after")
    def _scan_strings(self):
        for name, value in self:
            if isinstance(value, str):
                try:
                    _reject_labelling(value)
                except ValueError as e:
                    raise ValueError(f"{name}: {e}") from e
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        try:
                            _reject_labelling(item)
                        except ValueError as e:
                            raise ValueError(f"{name}: {e}") from e
        return self


# ---------------------------------------------------------------- Narrative Agent


class ExtractedObservation(_NoScoresNoLabels):
    """One thing pulled out of the narrative, with its kind and its certainty."""

    kind: ObservationKind
    text: str = Field(min_length=1)
    about: ObservationSubject = Field(
        default="unclear",
        description="Whose conduct this describes: the writer ('me'), the person being "
                    "assessed ('them'), both, or unclear. A Brain Dump about the "
                    "writer's own behavior must not become a page of open questions "
                    "about the other person.",
    )
    certainty: Certainty = "stated"
    hedge: str | None = Field(
        default=None,
        description="Required when certainty is 'inferred'. How to offer the reading "
                    "back for confirmation, e.g. 'It sounds like… Is that right?'",
    )

    @model_validator(mode="after")
    def _inference_must_hedge(self):
        if self.certainty == "inferred" and not (self.hedge or "").strip():
            raise ValueError(
                "An inferred observation must carry a hedge. Infer, but don't presume — "
                "a reading offered as a statement of fact is a presumption."
            )
        if self.certainty == "stated" and self.kind == "reported_event" and self.hedge:
            raise ValueError(
                "A stated reported_event must not be hedged; mark it inferred instead."
            )
        return self


class NarrativeOutput(_NoScoresNoLabels):
    """What the Narrative agent returns. No criteria here — mapping is Evidence's job."""

    observations: list[ExtractedObservation] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    user_conclusions: list[str] = Field(
        default_factory=list,
        description="Conclusions the user stated, kept separate so Reasoning can "
                    "interrogate them without the app having adopted them.",
    )
    themes: list[str] = Field(
        default_factory=list,
        description="What the entry was ABOUT, from the closed vocabulary in "
                    "data/themes.json. Not criteria, not judgments — topics. Empty is "
                    "a valid answer for an entry that fits none of them.",
    )

    @model_validator(mode="after")
    def _themes_are_in_the_vocabulary(self):
        """A closed vocabulary, enforced rather than requested.

        A model free to invent theme labels produces a different taxonomy every run, and
        "this keeps coming up" over an unstable vocabulary means nothing. Imported here
        rather than at module load so the contracts stay importable without the data
        file present.
        """
        if not self.themes:
            return self
        from .themes import UnknownTheme, validate

        try:
            object.__setattr__(self, "themes", validate(self.themes))
        except UnknownTheme as e:
            raise ValueError(f"themes: {e}") from e
        return self


# ---------------------------------------------------------------- Safety Layer


class SafetyOutput(_NoScoresNoLabels):
    """Runs on the raw narrative, alongside Narrative, independent of any profile."""

    concern_detected: bool = False
    category: SafetyCategory | None = None
    concern_level: ConcernLevel = "potential"
    rationale: str | None = Field(
        default=None,
        description="Why this behavior may be concerning, described behaviorally. "
                    "Never a diagnosis and never a label applied to a person.",
    )
    suggested_action: Literal["none", "note_only", "offer_resources", "halt_and_route"] = "none"
    safety_check: str | None = Field(
        default=None,
        description="A short, compassionate check for possible immediate danger — "
                    "'Are you safe right now?' Never a questionnaire.",
    )
    acknowledgement: str | None = Field(
        default=None,
        description="What to say first: acknowledges without judgment, before anything else.",
    )

    @model_validator(mode="after")
    def _coherent(self):
        if self.concern_detected and not (self.rationale or "").strip():
            raise ValueError("A detected concern must say why, in behavioral terms.")
        if not self.concern_detected and self.suggested_action in (
            "offer_resources", "halt_and_route"
        ):
            raise ValueError(
                "Resources or a halt were requested with no concern detected. Responding "
                "to a keyword rather than to what the person actually said is a failure "
                "in its own right."
            )
        if self.concern_level == "immediate_danger" and self.suggested_action != "halt_and_route":
            raise ValueError("Immediate danger must halt the ordinary workflow.")
        return self


# ---------------------------------------------------------------- Evidence Agent


class EvidenceMapping(_NoScoresNoLabels):
    """One observation's relation to one criterion, within the selected profile."""

    criterion_id: int
    observation_index: int = Field(
        ge=0, description="Index into the Narrative agent's observations list."
    )
    relation: EvidenceRelation
    rationale: str | None = None
    source_level: SourceLevel = "agent_hypothesis"
    research_ref: str | None = None

    @model_validator(mode="after")
    def _research_must_cite(self):
        if self.source_level in ("established_research", "research_informed") \
                and not (self.research_ref or "").strip():
            raise ValueError(
                "A research-backed mapping must carry a citation, so the user can see "
                "why the behavior was suggested."
            )
        return self


class InsufficientNote(_NoScoresNoLabels):
    criterion_id: int
    why: str = Field(min_length=1)


class EvidenceOutput(_NoScoresNoLabels):
    mappings: list[EvidenceMapping] = Field(default_factory=list)
    insufficient: list[InsufficientNote] = Field(
        default_factory=list,
        description="Criteria this entry touches but does not settle. A first-class "
                    "result, displayed, not an empty state.",
    )
    unmapped_observation_indexes: list[int] = Field(
        default_factory=list,
        description="Observations that relate to no criterion. They stay in the journal "
                    "without being assigned artificial significance — never force-fit.",
    )

    @model_validator(mode="after")
    def _collapse_repetition(self):
        """One mapping per (observation, criterion); one unsettled note per criterion.

        A test run produced twenty-five mapping rows for a single entry, of which a
        third said the same thing in different words — five separate rows ending "this
        does not establish whether she can live with that." Repetition is not more
        evidence; it reads as a case being built, and it buries the two or three rows
        that actually bear on something.

        This is deliberately the *narrow*, deterministic half of the fix: it removes
        exact structural duplicates only. Judging that two differently-worded rows make
        the same point is the Reasoning agent's job, and telling the model not to
        generate them in the first place is the prompt's — see `evidence.md`. Nothing
        here drops a row carrying information another row does not.
        """
        seen: set[tuple[int, int]] = set()
        kept = []
        for m in self.mappings:
            key = (m.observation_index, m.criterion_id)
            if key in seen:
                continue
            seen.add(key)
            kept.append(m)
        self.mappings = kept

        seen_criteria: set[int] = set()
        notes = []
        for n in self.insufficient:
            if n.criterion_id in seen_criteria:
                continue
            seen_criteria.add(n.criterion_id)
            notes.append(n)
        self.insufficient = notes
        return self


# ---------------------------------------------------------------- Reasoning Agent


class InterrogationQuestion(_NoScoresNoLabels):
    """Interrogation of the claim, never of the user."""

    claim: str = Field(min_length=1, description="The user's words, quoted.")
    claim_valence: Literal["negative", "positive", "neutral"] = "negative"
    gap_kind: GapKind
    question: str = Field(min_length=1)
    materiality: Literal["material", "optional"] = "material"


class CrossCriterionNote(_NoScoresNoLabels):
    """One behavior, several criteria, different relations — and no winner chosen."""

    observation_index: int = Field(ge=0)
    criterion_ids: list[int] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    competing: bool = False
    competing_question: str | None = Field(
        default=None,
        description="When criteria pull against each other, the question that hands the "
                    "weighing back to the user. KRYteria never decides which one wins.",
    )

    @model_validator(mode="after")
    def _competing_needs_a_question(self):
        if self.competing and not (self.competing_question or "").strip():
            raise ValueError(
                "Competing priorities must end in a question for the user. Naming a "
                "trade-off and then resolving it is deciding for her."
            )
        return self


class PatternFinding(_NoScoresNoLabels):
    kind: Literal[
        "recurring_unmet_need", "repeated_discrepancy", "shifting_expectation",
        "stated_vs_chosen", "insufficient_evidence",
    ]
    statement: str = Field(min_length=1)
    criterion_id: int | None = None
    supporting_entry_ids: list[int] = Field(default_factory=list)
    contradicting_entry_ids: list[int] = Field(default_factory=list)
    evidence_strength: EvidenceStrength = "limited"
    alternatives: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    gap_note: str | None = None

    @model_validator(mode="after")
    def _confident_findings_admit_doubt(self):
        if not self.supporting_entry_ids and not self.contradicting_entry_ids:
            raise ValueError(
                "A finding must name the journal entries it rests on. No evidence, no "
                "pattern."
            )
        if self.evidence_strength in ("moderate", "strong") and not [
            a for a in self.alternatives if a.strip()
        ]:
            raise ValueError(
                f"A '{self.evidence_strength}' finding must offer at least one "
                "alternative explanation. A finding that admits no other reading is a "
                "verdict, and KRYteria does not issue verdicts."
            )
        return self


class AssessmentProposal(_NoScoresNoLabels):
    """A suggestion. It is inert until the user accepts, rejects or edits it."""

    criterion_id: int
    proposed_status: AssessmentStatus
    rationale: str = Field(min_length=1)


class ReasoningOutput(_NoScoresNoLabels):
    interrogations: list[InterrogationQuestion] = Field(default_factory=list)
    cross_criterion: list[CrossCriterionNote] = Field(default_factory=list)
    patterns: list[PatternFinding] = Field(default_factory=list)
    proposals: list[AssessmentProposal] = Field(default_factory=list)

    @field_validator("interrogations")
    @classmethod
    def _dont_depose(cls, v):
        material = [q for q in v if q.materiality == "material"]
        if len(material) > 3:
            raise ValueError(
                f"{len(material)} material questions at once. Ask only where the missing "
                "information would change the assessment — nobody decompressing after a "
                "date should face a deposition."
            )
        return v


# ---------------------------------------------------------------- Reflection Agent


class Reconciliation(_NoScoresNoLabels):
    """Immediate feeling set beside accumulated evidence. Symmetrical, and not a verdict."""

    current_feeling: str = Field(min_length=1)
    broader_evidence: str = Field(min_length=1)
    tension: str | None = None


class ReflectionOutput(_NoScoresNoLabels):
    context: str | None = Field(
        default=None, description="The framing, e.g. 'Let's examine the discrepancy.'"
    )
    question: str = Field(min_length=1)
    alternatives: list[str] = Field(default_factory=list)
    reconciliation: Reconciliation | None = None
    is_postponement_probe: bool = False
    options: list[DecisionChoice] = Field(default_factory=list)
    cooldown_suggested: bool = False
    cooldown_summary_known: str | None = None
    cooldown_summary_unknown: str | None = None
    cooldown_would_help: str | None = None

    @model_validator(mode="after")
    def _cooldown_is_a_summary_not_a_shrug(self):
        if self.cooldown_suggested and not all([
            (self.cooldown_summary_known or "").strip(),
            (self.cooldown_summary_unknown or "").strip(),
            (self.cooldown_would_help or "").strip(),
        ]):
            raise ValueError(
                "A cooldown must summarize what is known, what is unknown, and what would "
                "change it. Without those three it is just telling someone to stop talking."
            )
        return self


# ---------------------------------------------------------------- Criteria Agent


class BehavioralIndicator(_NoScoresNoLabels):
    text: str = Field(min_length=1)
    polarity: Literal["demonstrates", "contradicts"] = "demonstrates"
    source_level: SourceLevel = "research_informed"
    research_ref: str | None = None

    @model_validator(mode="after")
    def _research_must_cite(self):
        if self.source_level in ("established_research", "research_informed") \
                and not (self.research_ref or "").strip():
            raise ValueError(
                f"Indicator {self.text[:40]!r} claims a research basis but cites nothing."
            )
        return self


class CriteriaOutput(_NoScoresNoLabels):
    clarification: str | None = Field(
        default=None,
        description="A suggested clearer wording. A SUGGESTION — the user's wording is "
                    "never silently rewritten.",
    )
    ambiguities: list[str] = Field(default_factory=list)
    indicators: list[BehavioralIndicator] = Field(default_factory=list)


# ---------------------------------------------------------------- Orchestrator


class RouteDecision(_NoScoresNoLabels):
    """Which agents this request actually needs. Fewer calls is the default."""

    needs_reasoning: bool = False
    needs_reflection: bool = False
    why: str | None = None
