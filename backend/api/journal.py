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
    BrainDump, EvidenceLinkDecision, InterrogationAnswer, PersonIn, RetentionChoice,
    StructuredEntry, UserEvidenceLink,
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

@router.get("/people/{person_id}/footprint")
def person_footprint(
    person_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """What removing this person would take with them — asked before, not discovered after."""
    owned_person(store, account_id, person_id)
    return store.person_footprint(account_id, person_id)


@router.delete("/people/{person_id}")
def delete_person(
    person_id: int,
    delete_entries: bool = False,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Remove a person.

    Their assessments always go — a Pass or Fail means nothing without the person it is
    about. Entries survive unless ``delete_entries`` is set, because an entry is the
    user's own writing about their own life.
    """
    owned_person(store, account_id, person_id)
    result = store.delete_person(account_id, person_id, delete_entries=delete_entries)
    return {
        **result,
        "note": ("Removed, along with everything you'd written about them."
                 if delete_entries else
                 "Removed. What you wrote is still in your journal, no longer "
                 "attached to anybody."),
    }


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
            people=body.people, person_id=body.person_id,
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
            person_id=body.person_id,
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))

    if not body.analyze:
        # Retention describes what survives PROCESSING. With nothing processed,
        # `analysis_only` would erase the narrative and leave no analysis behind it —
        # destroying the only thing the user just created, which cannot be what "save
        # without analysing" means. So the default collapses to keeping it.
        #
        # An explicit `discard` is still honoured: somebody may genuinely want to write
        # something down and have it gone.
        retention = (
            store.apply_retention(account_id, entry_id, "discard")
            if body.retention == "discard"
            else store.apply_retention(account_id, entry_id, "keep_all")
        )
        return {
            "entry": store.get_entry(account_id, entry_id),
            "analysis": None,
            "retention": retention,
            "note": ("Saved without analysis. Nothing was processed, so the entry is "
                     "kept as written." if body.retention != "discard" else
                     "Saved, then discarded as requested. Nothing remains."),
        }
    entry = store.get_entry(account_id, entry_id)

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

    # Retention is applied AFTER processing: the agents need the narrative to read it,
    # and the user's choice governs what survives that reading. Doing it here rather
    # than relying on a later sweep means the window in which an unwanted original sits
    # in the database is the length of one request.
    retention = store.apply_retention(account_id, entry_id, body.retention)

    return {
        "entry": store.get_entry(account_id, entry_id) or entry,
        "analysis": _present(result),
        "simulated": info.simulated,
        "retention": retention,
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
        # **Withheld from this screen, not withheld from her record.**
        #
        # Everything the agents extracted has already been written: observations,
        # themes, evidence mappings. What does not happen is showing a compatibility
        # analysis in the same breath as "are you safe right now?" — the charter's
        # *"never return to ordinary compatibility analysis as though nothing
        # significant was said."*
        #
        # It is reported rather than hidden, because a silent omission is its own kind
        # of dishonesty: she wrote something down and is entitled to know it was kept
        # and where to find it when she wants it.
        payload["halt_reason"] = result.halt_reason
        payload["analysis_withheld"] = True
        payload["analysis_recorded"] = {
            "observations": len(result.narrative.observations) if result.narrative else 0,
            "mappings": len(result.evidence.mappings) if result.evidence else 0,
            "where": f"/api/entries/{result.entry_id}" if result.entry_id else None,
        }
        payload["note"] = (
            "What you wrote has been saved and the details recorded, including what it "
            "says about your criteria. That part is set aside for now — it is on this "
            "entry whenever you want it. Right now this is about you."
        )
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

@router.post("/entries/{entry_id}/retention")
def choose_retention(
    entry_id: int,
    body: RetentionChoice,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Change the mind after the fact: *"What would you like KRYteria to keep?"*

    Offered once the analysis is on screen, so somebody can see what the reflection
    produced before deciding whether the 1 a.m. narrative behind it is worth keeping.

    Only ever erases further. There is no path back from a discarded narrative, and the
    response says so plainly rather than letting somebody discover it later.
    """
    owned_entry(store, account_id, entry_id)
    try:
        result = store.apply_retention(account_id, entry_id, body.retention)
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))

    swept = 0
    if body.apply_to_past:
        store.set_preferences(account_id, retention=body.retention)
        swept = store.erase_originals(account_id)

    return {
        "entry_id": entry_id,
        **result,
        "also_erased": swept,
        "note": ("The original has been erased and cannot be recovered."
                 if result["original_erased"] else
                 "The original is kept until you delete it."),
    }


@router.get("/retention")
def retention_report(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """What KRYteria is actually keeping, counted from the data rather than promised."""
    return store.retention_report(account_id)


@router.post("/evidence-links", status_code=status.HTTP_201_CREATED)
def create_evidence_link(
    body: UserEvidenceLink,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """The user's own mapping of an entry to a criterion.

    Arrives **accepted**, unlike an agent's: there is nothing to confirm when the person
    whose life it is made the link themselves. It also costs no model call, which is why
    Quick Log is both cheaper and more accurate than asking an agent to infer the same
    thing.
    """
    owned_entry(store, account_id, body.entry_id)
    if body.profile_id is not None:
        owned_profile(store, account_id, body.profile_id)
    try:
        link_id = store.link_evidence(
            account_id, entry_id=body.entry_id, criterion_id=body.criterion_id,
            relation=body.relation, profile_id=body.profile_id,
            person_id=body.person_id, rationale=body.rationale,
            source_level="user_stated", proposed_by="user",
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return {"id": link_id, "relation": body.relation}


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
