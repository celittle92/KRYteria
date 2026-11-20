"""The master criteria library, KRYteria Profiles, and Checklist Mode.

Three levels, kept apart:

  * ``/api/criteria``  — the library. Reusable standards, no tier, no profile.
  * ``/api/profiles``  — configurations that select criteria and assign this profile's
                         tier and relevance.
  * ``/api/profiles/{id}/criteria`` — the join, where a tier actually lives.

Editing one profile cannot reach into another. Copying is an explicit action that
duplicates settings and records provenance.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from ..paste import parse_paste
from ..store import NotOwned, Store, StoreError
from .deps import (
    current_account_id, get_provider, get_store, owned_criterion, owned_profile,
)
from .schemas import (
    ChecklistObservationIn, CopyCriteria, CriteriaBulk, CriterionIn, CriterionRevision,
    IndicatorRequest, PasteIn, ProfileCriteriaBulk, ProfileCriterionIn, ProfileEdit,
    ProfileIn, TierChange,
)

router = APIRouter(prefix="/api", tags=["criteria"])


# ---------------------------------------------------------------- the library

@router.get("/criteria")
def list_criteria(
    status_filter: str = "active",
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    return store.list_criteria(account_id, status=status_filter)


@router.post("/criteria", status_code=status.HTTP_201_CREATED)
def create_criterion(
    body: CriterionIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Create a standard.

    Nothing here judges whether a criterion is reasonable. "Soft hands" is as valid as
    "compatible relationship intentions"; the user's standards are theirs.
    """
    cid = store.create_criterion(
        account_id, value=body.value, desired_behavior=body.desired_behavior,
        why_it_matters=body.why_it_matters, examples=body.examples,
    )
    return next(c for c in store.list_criteria(account_id, status="all") if c["id"] == cid)


@router.post("/criteria/parse")
def parse_criteria_paste(
    body: PasteIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Parse a pasted list of standards. **Writes nothing.**

    Somebody who already knows what they want has usually already written it down
    somewhere. This reads that list and shows back what it made of it — including the
    lines it could not use and the ones already in her library — so she can correct it
    before a single row is created. ``/api/criteria/bulk`` is the step that writes.

    There is no model call here, and that is a product decision as much as a cost one: a
    model asked to tidy up somebody's standards will improve them, and they are not ours
    to improve.
    """
    existing = [c["value"] for c in store.list_criteria(account_id)]
    result = parse_paste(body.text, existing=existing)
    return {
        "lines": [asdict(line) for line in result.lines],
        "ready": len(result.ready),
    }


@router.post("/criteria/bulk", status_code=status.HTTP_201_CREATED)
def create_criteria(
    body: CriteriaBulk,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Create several criteria at once, after the user has reviewed them.

    One transaction: all of them land or none do. Half a pasted list, with no way to tell
    which half, is worse than an error.
    """
    try:
        created = store.create_criteria(
            account_id, [item.model_dump() for item in body.items]
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    by_id = {c["id"]: c for c in store.list_criteria(account_id, status="all")}
    return {"created": len(created), "criteria": [by_id[i] for i in created]}


@router.post("/criteria/{criterion_id}/revise")
def revise_criterion(
    criterion_id: int,
    body: CriterionRevision,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Write a new version. The old one is superseded, never overwritten.

    How somebody's standards changed over time is among the most useful things this app
    can show them, and an in-place edit destroys it.
    """
    owned_criterion(store, account_id, criterion_id)
    changes = {k: v for k, v in body.model_dump(exclude={"revision_note"}).items()
               if v is not None}
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nothing to revise.")
    try:
        new_id = store.revise_criterion(
            account_id, criterion_id, revision_note=body.revision_note, **changes
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return next(c for c in store.list_criteria(account_id, status="all")
                if c["id"] == new_id)


@router.get("/criteria/{criterion_id}/history")
def criterion_history(
    criterion_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Every version, oldest first — the 'changing priorities' view."""
    criterion = owned_criterion(store, account_id, criterion_id)
    return store.criterion_history(account_id, criterion["lineage_id"])


@router.delete("/criteria/{criterion_id}")
def retire_criterion(
    criterion_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Retire, not delete. The history and any evidence linked to it survive."""
    owned_criterion(store, account_id, criterion_id)
    store.retire_criterion(account_id, criterion_id)
    return {"retired": criterion_id}


# ---------------------------------------------------------------- profiles

@router.get("/profiles")
def list_profiles(
    include_archived: bool = False,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    profiles = store.list_profiles(account_id, include_archived=include_archived)
    for p in profiles:
        p["criteria_count"] = len(store.list_profile_criteria(account_id, p['id']))
    return profiles


@router.post("/profiles", status_code=status.HTTP_201_CREATED)
def create_profile(
    body: ProfileIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Any number of profiles, any names. Nothing here ranks one above another."""
    try:
        pid = store.create_profile(
            account_id, body.name, objective=body.objective,
            context_label=body.context_label, domain_id=body.domain_id,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "You already have a profile with that name.")
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return owned_profile(store, account_id, pid)


@router.patch("/profiles/{profile_id}")
def update_profile(
    profile_id: int,
    body: ProfileEdit,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Rename a profile, or change what it is for.

    A rename invalidates nothing — every criterion, tier, assessment and history row
    stays exactly where it is. People's lives move and the labels they chose months ago
    stop fitting; a product built on "your standards are yours" has no business making
    that permanent.
    """
    owned_profile(store, account_id, profile_id)
    try:
        store.update_profile(account_id, profile_id, name=body.name,
                             objective=body.objective,
                             context_label=body.context_label)
    except StoreError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    return owned_profile(store, account_id, profile_id)


@router.post("/profiles/{profile_id}/archive")
def archive_profile(
    profile_id: int,
    archived: bool = True,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Put a profile away, or bring it back. **Nothing is destroyed.**

    There is deliberately no per-profile delete. A profile holds the assessments made
    under it — the record of what somebody thought at the time — and that is the thing
    this product exists to keep. Archiving hides it everywhere and is reversible; the
    genuine need to erase is met by `POST /api/account/delete`, at the level where
    consent to it is meaningful.
    """
    owned_profile(store, account_id, profile_id)
    store.set_profile_archived(account_id, profile_id, archived)
    return {
        "profile_id": profile_id,
        "archived": archived,
        "note": ("Put away. Everything assessed under it is kept, and you can bring it "
                 "back whenever you like." if archived
                 else "Back in use, exactly as you left it."),
    }


@router.get("/profiles/{profile_id}/criteria")
def list_profile_criteria(
    profile_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    owned_profile(store, account_id, profile_id)
    return store.list_profile_criteria(account_id, profile_id)


@router.post("/profiles/{profile_id}/criteria", status_code=status.HTTP_201_CREATED)
def add_criterion_to_profile(
    profile_id: int,
    body: ProfileCriterionIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    owned_profile(store, account_id, profile_id)
    owned_criterion(store, account_id, body.criterion_id)
    try:
        store.add_criterion_to_profile(
            account_id, profile_id, body.criterion_id, tier=body.tier, relevance=body.relevance,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "That criterion is already on this profile.")
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return store.list_profile_criteria(account_id, profile_id)


@router.post("/profiles/{profile_id}/criteria/bulk", status_code=status.HTTP_201_CREATED)
def add_criteria_to_profile(
    profile_id: int,
    body: ProfileCriteriaBulk,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Add many library criteria to this profile — "add all", or a chosen subset.

    With one profile, the library and the profile are usually the same list, and clicking
    eighteen pills is busywork rather than a decision. Removing the ones that do not
    belong here is the decision, and it stays one click each.

    Everything arrives at the same neutral tier. Mandatory means a failure is potentially
    disqualifying, and that is the user's call to make per criterion, not a side effect of
    a convenience button. Anything already on the profile keeps the settings it has.
    """
    owned_profile(store, account_id, profile_id)
    try:
        result = store.add_criteria_to_profile(
            account_id, profile_id, body.criterion_ids, tier=body.tier,
        )
    except NotOwned as e:
        # Another account's criterion is a 404, exactly as a single add would be.
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return {
        "added": len(result["added"]),
        "already_there": result["already_there"],
        "criteria": store.list_profile_criteria(account_id, profile_id),
    }


@router.patch("/profiles/{profile_id}/criteria/{criterion_id}")
def set_tier(
    profile_id: int,
    criterion_id: int,
    body: TierChange,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Change a tier **in this profile only**.

    Physical attraction can be Preferred for a husband and Mandatory for a one-night
    stand. Both are legitimate, and changing one must never touch the other.
    """
    owned_profile(store, account_id, profile_id)
    owned_criterion(store, account_id, criterion_id)
    if body.tier is None and body.relevance is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Send a tier, a relevance, or both.")
    try:
        if body.tier is not None:
            store.set_profile_tier(account_id, profile_id, criterion_id, body.tier)
        if body.relevance is not None:
            store.set_profile_relevance(account_id, profile_id, criterion_id,
                                        body.relevance)
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return store.list_profile_criteria(account_id, profile_id)


@router.post("/profiles/{profile_id}/copy-criteria")
def copy_criteria(
    profile_id: int,
    body: CopyCriteria,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Copy settings from another profile. A copy, not a link.

    The two profiles are independent afterwards; provenance is recorded so the user can
    see where the settings came from.
    """
    owned_profile(store, account_id, profile_id)
    owned_profile(store, account_id, body.source_profile_id)
    try:
        created = store.copy_criteria_to_profile(
            account_id, body.source_profile_id, profile_id, body.criterion_ids
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return {"copied": len(created), "criteria": store.list_profile_criteria(account_id, profile_id)}


# ---------------------------------------------------------------- checklist mode

@router.get("/criteria/{criterion_id}/checklist")
def get_checklist(
    criterion_id: int,
    profile_id: int | None = None,
    person_id: int | None = None,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    owned_criterion(store, account_id, criterion_id)
    if profile_id is not None:
        owned_profile(store, account_id, profile_id)
    return store.list_checklist(account_id, criterion_id, profile_id=profile_id,
                                person_id=person_id)


@router.post("/criteria/{criterion_id}/checklist/generate")
async def generate_checklist(
    criterion_id: int,
    body: IndicatorRequest,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Direction A: turn a criterion into observable behavioral indicators.

    One model call. Off the brain-dump path, so it costs nothing on a journal entry.
    """
    from ..agents.orchestrator import BudgetExceeded, Orchestrator

    criterion = owned_criterion(store, account_id, criterion_id)
    profile = owned_profile(store, account_id, body.profile_id) if body.profile_id else None
    model, info = get_provider()
    orch = Orchestrator(store, model, info)
    try:
        step = await orch.clarify_criterion(
            account_id, value=criterion["value"],
            desired_behavior=criterion["desired_behavior"],
            why_it_matters=criterion["why_it_matters"],
            profile_name=profile["name"] if profile else None,
        )
    except BudgetExceeded as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e))
    if not step.ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            f"The criteria agent could not produce indicators: {step.error}")
    saved = store.save_checklist_items(
        account_id, criterion_id,
        [i.model_dump() for i in step.output.indicators],
        profile_id=body.profile_id,
    )
    return {
        "clarification": step.output.clarification,
        "ambiguities": step.output.ambiguities,
        "indicators": store.list_checklist(account_id, criterion_id,
                                           profile_id=body.profile_id),
        "saved": len(saved),
    }


@router.post("/checklist/{item_id}/observe", status_code=status.HTTP_201_CREATED)
def observe_indicator(
    item_id: int,
    body: ChecklistObservationIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Record what was seen.

    This records an observation. It does **not** move the criterion's status — there is
    no code path from here to an assessment. Only the user sets Pass.
    """
    try:
        obs_id = store.record_checklist_observation(
            account_id, item_id, person_id=body.person_id, entry_id=body.entry_id,
            state=body.state, note=body.note, occurred_on=body.occurred_on,
        )
    except NotOwned as e:
        # Reaching another account's row is a 404, never a 403 and never a 422:
        # `store.NotOwned` says so and every sibling route honors it. This one did
        # not, because until the ownership assert was added the only StoreError it
        # could raise was a bad `state`. A new exception took the old exit.
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return {
        "observation_id": obs_id,
        "note": "Recorded as an observation. It does not change the criterion's status.",
    }
