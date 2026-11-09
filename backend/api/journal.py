"""The journal: brain dump, structured entries, and reviewing what the agents proposed.

The brain dump is the primary interaction, so this is the route that matters most. It
always saves the entry first and analyses second — a model failure, a budget refusal or a
provider outage must never cost somebody the thing they just wrote.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..store import Store, StoreError
from .deps import (
    current_account_id, get_provider, get_store, owned_entry, owned_person, owned_profile,
    resolve_domain,
)
from .schemas import (
    BrainDump, EvidenceLinkDecision, InterrogationAnswer, PersonIn, StructuredEntry,
)

router = APIRouter(prefix="/api", tags=["journal"])


# ---------------------------------------------------------------- people

@router.get("/people")
def list_people(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    return store.list_people(account_id)


@router.post("/people", status_code=status.HTTP_201_CREATED)
def create_person(
    body: PersonIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """An alias the user chose. There is no column for a real name."""
    try:
        pid = store.upsert_person(account_id, body.alias, domain_id=body.domain_id,
                                  role_label=body.role_label)
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return next(p for p in store.list_people(account_id) if p["id"] == pid)


# ---------------------------------------------------------------- entries

@router.get("/entries")
def list_entries(
    limit: int = 50,
    search: str | None = None,
    since: str | None = None,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    return store.list_entries(account_id, limit=min(limit, 500), search=search, since=since)


@router.get("/entries/{entry_id}")
def get_entry(
    entry_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    entry = owned_entry(store, account_id, entry_id)
    entry["observations"] = store.list_observations(account_id, entry_ids=[entry_id])
    entry["evidence_links"] = store.list_evidence_links(account_id, entry_id=entry_id)
    entry["questions"] = store.list_interrogations(account_id, entry_id=entry_id)
    return entry


@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    owned_entry(store, account_id, entry_id)
    store.delete_entry(account_id, entry_id)
    return {"deleted": entry_id}


@router.post("/entries/structured", status_code=status.HTTP_201_CREATED)
def create_structured_entry(
    body: StructuredEntry,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Structured entry. First-class, not a fallback — some people prefer fields."""
    profile = owned_profile(store, account_id, body.profile_id) if body.profile_id else None
    domain_id = resolve_domain(store, account_id, body.domain_id, profile)
    try:
        entry_id = store.create_entry(
            account_id, domain_id, occurred_on=body.occurred_on, entry_mode="structured",
            what_happened=body.what_happened, what_expected=body.what_expected,
            how_it_affected=body.how_it_affected, witness=body.witness,
            people=body.people,
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return store.get_entry(account_id, entry_id)


# ---------------------------------------------------------------- the brain dump

@router.post("/brain-dump", status_code=status.HTTP_201_CREATED)
async def brain_dump(
    body: BrainDump,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Write something down, and optionally have the agents read it.

    **The entry is saved before any model call.** If the budget refuses, the provider is
    down, or the model returns something malformed, the user still has what they wrote.
    Losing somebody's writing because an API failed would be the worst bug this app could
    have.
    """
    from ..agents.orchestrator import BudgetExceeded, Orchestrator

    profile = owned_profile(store, account_id, body.profile_id) if body.profile_id else None
    if body.person_id is not None:
        owned_person(store, account_id, body.person_id)
    domain_id = resolve_domain(store, account_id, body.domain_id, profile)

    try:
        entry_id = store.create_entry(
            account_id, domain_id, occurred_on=body.occurred_on, entry_mode="free",
            body=body.text, witness=body.witness, people=body.people,
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))

    entry = store.get_entry(account_id, entry_id)
    if not body.analyze:
        return {"entry": entry, "analysis": None,
                "note": "Saved without analysis, as requested."}

    model, info = get_provider()
    orch = Orchestrator(store, model, info)
    try:
        result = await orch.brain_dump(
            account_id, entry_id=entry_id, entry_text=body.text,
            profile_id=body.profile_id,
            profile_name=profile["name"] if profile else "",
            person_id=body.person_id, want_reflection=body.want_reflection,
            occurred_on=body.occurred_on,
        )
    except BudgetExceeded as e:
        # The entry is already saved; say so rather than implying it was lost.
        return {
            "entry": entry, "analysis": None, "budget_exceeded": True,
            "note": f"Your entry is saved. {e}",
        }

    return {
        "entry": entry,
        "analysis": _present(result),
        "simulated": info.simulated,
    }


def _present(result) -> dict:
    """Shape the orchestrator's result for the browser.

    Resources and the safety acknowledgement come first when the safety layer fired —
    the ordinary analysis is not the headline when somebody has just described being hurt.
    """
    safety = result.safety
    payload: dict = {
        "run_id": result.run_id,
        "status": result.status,
        "halted": result.halted,
        "model_calls": result.model_calls,
        "errors": result.errors,
    }

    if safety is not None:
        payload["safety"] = {
            "concern_detected": safety.concern_detected,
            "category": safety.category,
            "concern_level": safety.concern_level,
            "acknowledgement": safety.acknowledgement,
            "safety_check": safety.safety_check,
            "rationale": safety.rationale,
        }
        payload["resources"] = result.resources
    if result.halted:
        payload["halt_reason"] = result.halt_reason
        return payload

    if result.narrative is not None:
        payload["observations"] = [o.model_dump() for o in result.narrative.observations]
        payload["missing_information"] = result.narrative.missing_information
        payload["uncertainties"] = result.narrative.uncertainties
    if result.evidence is not None:
        payload["mappings"] = [m.model_dump() for m in result.evidence.mappings]
        payload["insufficient"] = [i.model_dump() for i in result.evidence.insufficient]
        payload["unmapped"] = result.evidence.unmapped_observation_indexes
    if result.reasoning is not None:
        payload["questions"] = [q.model_dump() for q in result.reasoning.interrogations]
        payload["cross_criterion"] = [c.model_dump()
                                      for c in result.reasoning.cross_criterion]
        payload["patterns"] = [p.model_dump() for p in result.reasoning.patterns]
        payload["proposals"] = [p.model_dump() for p in result.reasoning.proposals]
    if result.reflection is not None:
        payload["reflection"] = result.reflection.model_dump()
    return payload


# ---------------------------------------------------------------- reviewing the agent

@router.get("/evidence-links")
def list_evidence_links(
    resolution: str | None = None,
    criterion_id: int | None = None,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    return store.list_evidence_links(account_id, resolution=resolution,
                                     criterion_id=criterion_id)


@router.patch("/evidence-links/{link_id}")
def decide_evidence_link(
    link_id: int,
    body: EvidenceLinkDecision,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Accept, reject, or edit a mapping the agent proposed.

    Editing lets the user pick a different relation from the one suggested — the mapping
    is a suggestion about their life, not a fact about it.
    """
    existing = [l for l in store.list_evidence_links(account_id) if l["id"] == link_id]
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such evidence link.")
    try:
        store.resolve_evidence_link(account_id, link_id, body.resolution,
                                    relation=body.relation)
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return [l for l in store.list_evidence_links(account_id) if l["id"] == link_id][0]


@router.get("/questions")
def list_questions(
    unanswered_only: bool = True,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    return store.list_interrogations(account_id, unanswered_only=unanswered_only)


@router.post("/questions/{question_id}/answer")
def answer_question(
    question_id: int,
    body: InterrogationAnswer,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Answer, or decline. Declining is always allowed and is not asked again."""
    existing = [q for q in store.list_interrogations(account_id) if q["id"] == question_id]
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such question.")
    store.answer_interrogation(account_id, question_id, body.answer)
    return {"answered": question_id, "declined": body.answer is None}


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """The execution trace: what each agent did, what it cost, how long it took.

    Shown in the app, which is also how the agent-design and tokenomics evidence becomes
    a screenshot instead of a scramble through logs. Carries tool names and token counts
    only — never raw journal text.
    """
    trace = store.get_run(account_id, run_id)
    if trace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    return trace
