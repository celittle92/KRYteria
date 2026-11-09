"""Request and response bodies for the HTTP API.

Separate from ``backend/models.py``, which holds the *agent* output contracts. These are
what the browser sends and receives; those are what a model must produce. Keeping them
apart means a change to the wire format cannot quietly loosen a validator that the product
depends on.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["mandatory", "preferred", "aspirational"]
Relevance = Literal["relevant", "not_applicable"]
Status = Literal["pass", "unknown", "fail", "not_applicable"]
Relation = Literal["supporting", "contradicting", "complicating", "unrelated"]
Resolution = Literal["accepted", "rejected", "edited"]
Choice = Literal["talk", "boundary", "more_time", "gather_info", "reconsider",
                 "revise_criterion", "undecided"]


# ---------------------------------------------------------------- auth

class SignUp(BaseModel):
    """No email, no name. A handle the user chose and a passphrase."""

    handle: str = Field(min_length=1, max_length=60)
    passphrase: str = Field(min_length=10, max_length=256)


class SignIn(BaseModel):
    handle: str
    passphrase: str


Retention = Literal["discard", "analysis_only", "keep_all"]


class Preferences(BaseModel):
    tone_mode: Literal["clarity", "tough_love"] | None = None
    theme: Literal["dark", "warm"] | None = None
    resource_offering: Literal["proactive", "on_request", "suppressed"] | None = None
    retention: Retention | None = Field(
        default=None,
        description="What KRYteria keeps after processing a brain dump. Set once here "
                    "rather than answered every time; each dump can still override it.",
    )


class RetentionChoice(BaseModel):
    """The choice offered after a brain dump has been processed.

    discard       — the narrative and everything derived from it go
    analysis_only — the narrative is erased; observations and mappings survive
    keep_all      — everything stays until the user deletes it
    """

    retention: Retention
    apply_to_past: bool = Field(
        default=False,
        description="Also apply this to entries already written whose originals have "
                    "not yet been erased.",
    )


# ---------------------------------------------------------------- criteria library

class CriterionIn(BaseModel):
    value: str = Field(min_length=1, max_length=200)
    desired_behavior: str = Field(min_length=1, max_length=1000)
    why_it_matters: str | None = Field(default=None, max_length=2000)
    examples: list[str] = Field(default_factory=list)


class CriterionRevision(BaseModel):
    """A revision writes a new version; it never edits the old row in place."""

    value: str | None = None
    desired_behavior: str | None = None
    why_it_matters: str | None = None
    examples: list[str] | None = None
    revision_note: str | None = Field(
        default=None,
        description="Why the user changed it, in their words. Kept with the old version.",
    )


# ---------------------------------------------------------------- profiles

class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    objective: str | None = Field(default=None, max_length=500)
    context_label: str | None = Field(default=None, max_length=60)
    domain_id: int | None = None


class ProfileCriterionIn(BaseModel):
    criterion_id: int
    tier: Tier = "preferred"
    relevance: Relevance = "relevant"


class TierChange(BaseModel):
    tier: Tier


class CopyCriteria(BaseModel):
    """Copying is explicit and produces an independent configuration."""

    source_profile_id: int
    criterion_ids: list[int] | None = None


# ---------------------------------------------------------------- people

class PersonIn(BaseModel):
    alias: str = Field(min_length=1, max_length=80,
                       description="An alias the user chose. Never a real name.")
    role_label: str | None = Field(default=None, max_length=120)
    domain_id: int | None = None


# ---------------------------------------------------------------- journal

class BrainDump(BaseModel):
    """The primary interaction. Everything except the text is optional."""

    text: str = Field(min_length=1, max_length=20_000)
    profile_id: int | None = None
    person_id: int | None = None
    domain_id: int | None = None
    occurred_on: str | None = None
    witness: Literal["firsthand", "inferred", "secondhand"] = "firsthand"
    people: list[str] = Field(default_factory=list)
    want_reflection: bool = False
    retention: Literal["discard", "analysis_only", "keep_all"] | None = Field(
        default=None,
        description="Override the account default for this dump only. Null uses the "
                    "account's setting. Applied AFTER processing, so the agents still "
                    "see the narrative they need to read.",
    )
    analyze: bool = Field(
        default=True,
        description="False saves the entry without spending a model call. Writing "
                    "something down is useful even when nobody analyses it.",
    )


class StructuredEntry(BaseModel):
    what_happened: str | None = None
    what_expected: str | None = None
    how_it_affected: str | None = None
    profile_id: int | None = None
    person_id: int | None = None
    domain_id: int | None = None
    occurred_on: str | None = None
    witness: Literal["firsthand", "inferred", "secondhand"] = "firsthand"
    people: list[str] = Field(default_factory=list)


class UserEvidenceLink(BaseModel):
    """A mapping the user made themselves, rather than one an agent proposed."""

    entry_id: int
    criterion_id: int
    relation: Relation
    profile_id: int | None = None
    person_id: int | None = None
    rationale: str | None = None


class EvidenceLinkDecision(BaseModel):
    """The user accepts, rejects or edits every agent-proposed mapping."""

    resolution: Resolution
    relation: Relation | None = None


class InterrogationAnswer(BaseModel):
    answer: str | None = Field(
        default=None,
        description="Null declines the question. Declining is always allowed and the "
                    "question is not asked again.",
    )


# ---------------------------------------------------------------- assessment

class AssessmentIn(BaseModel):
    """Only the user reaches this. No agent code path writes an assessment status."""

    profile_id: int
    criterion_id: int
    person_id: int
    status: Status
    note: str | None = None


class ProposalDecision(BaseModel):
    resolution: Resolution
    final_status: Status | None = Field(
        default=None,
        description="Required when editing — the status the user chose, which may differ "
                    "from the one the agent proposed.",
    )


class DecisionIn(BaseModel):
    choice: Choice
    action_text: str | None = None
    reflection_id: int | None = None
    pattern_id: int | None = None
    criterion_id: int | None = None
    revisit_on: str | None = None


class PatternStatusIn(BaseModel):
    status: Literal["open", "addressed", "dismissed"]


# ---------------------------------------------------------------- checklist

class ChecklistObservationIn(BaseModel):
    """Recording an observation. It never moves a criterion's status."""

    person_id: int | None = None
    entry_id: int | None = None
    state: Literal["observed", "not_observed", "contradicted", "no_opportunity"] = "observed"
    note: str | None = None
    occurred_on: str | None = None


class IndicatorRequest(BaseModel):
    criterion_id: int
    profile_id: int | None = None


# ---------------------------------------------------------------- safety

class ResourceOfferResponse(BaseModel):
    """A decline is respected and not re-raised."""

    response: Literal["accepted", "declined", "ignored"]


# ---------------------------------------------------------------- account

class DeleteAccount(BaseModel):
    """Deletion removes rows rather than flagging them, so it asks for the passphrase."""

    passphrase: str
    confirm: Literal["DELETE EVERYTHING"]
