"""Assessments, proposals, patterns, decisions, and the My Progress view.

The rule this module exists to enforce: **only the user sets a status.** Agents write to
``assessment_proposals``; the single route that moves a real status is
``PUT /api/assessments``, which no agent can reach.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..store import Store, StoreError
from .deps import (
    current_account_id, get_store, owned_criterion, owned_person, owned_profile,
)
from .schemas import AssessmentIn, DecisionIn, PatternStatusIn, ProposalDecision

router = APIRouter(prefix="/api", tags=["assessment"])


# ---------------------------------------------------------------- assessments

@router.get("/assessments")
def assessment_board(
    profile_id: int,
    person_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """This profile's criteria with this person's status against each.

    Scoped to one profile and never falling back to another. The same person under
    Husband KRYteria and under One Night Stand KRYteria has two independent answers.
    """
    owned_profile(store, account_id, profile_id)
    owned_person(store, account_id, person_id)
    return store.assessment_board(account_id, profile_id, person_id)


@router.put("/assessments")
def set_assessment(
    body: AssessmentIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Set Pass / Unknown / Fail / Not Applicable.

    The only route in the application that moves a status, and it is reachable only by a
    signed-in user acting on their own data. Every transition is recorded with its
    previous value, origin and explanation.
    """
    owned_profile(store, account_id, body.profile_id)
    owned_criterion(store, account_id, body.criterion_id)
    owned_person(store, account_id, body.person_id)
    try:
        assessment_id = store.set_assessment(
            account_id, body.profile_id, body.criterion_id, body.person_id,
            body.status, note=body.note, origin="user",
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return {
        "assessment_id": assessment_id,
        "status": body.status,
        "history": store.assessment_history(account_id, assessment_id),
    }


@router.get("/assessments/{assessment_id}/history")
def assessment_history(
    assessment_id: int,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    history = store.assessment_history(account_id, assessment_id)
    if not history:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such assessment.")
    return history


# ---------------------------------------------------------------- proposals

@router.get("/proposals")
def list_proposals(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """What the agents suggested and the user has not yet acted on.

    A pending proposal is inert. Nothing in the app reads one as though it were a status.
    """
    return store.list_pending_proposals(account_id)


@router.post("/proposals/{proposal_id}/decide")
def decide_proposal(
    proposal_id: int,
    body: ProposalDecision,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Accept, reject, or edit.

    Editing applies the status the **user** chose, which may be neither the current one
    nor the one the agent proposed.
    """
    if body.resolution == "edited" and body.final_status is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Editing a proposal must name the status you chose.")
    try:
        store.resolve_proposal(account_id, proposal_id, body.resolution,
                               final_status=body.final_status)
    except StoreError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return {"proposal_id": proposal_id, "resolution": body.resolution}


# ---------------------------------------------------------------- patterns

@router.get("/patterns")
def list_patterns(
    profile_id: int | None = None,
    status_filter: str = "open",
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Findings with their evidence — and their counter-evidence, separately.

    ``insufficient`` findings are returned too. "I don't have enough to say" is a result
    the user is entitled to see, not an empty state to hide.
    """
    if profile_id is not None:
        owned_profile(store, account_id, profile_id)
    return store.list_patterns(account_id, profile_id=profile_id, status=status_filter)


@router.patch("/patterns/{pattern_id}")
def set_pattern_status(
    pattern_id: int,
    body: PatternStatusIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """The user can dismiss a finding. They are the authority on their own experience."""
    try:
        store.set_pattern_status(account_id, pattern_id, body.status)
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return {"pattern_id": pattern_id, "status": body.status}


# ---------------------------------------------------------------- decisions

@router.get("/decisions")
def list_decisions(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    return store.list_decisions(account_id)


@router.post("/decisions", status_code=status.HTTP_201_CREATED)
def record_decision(
    body: DecisionIn,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Record what the user chose to do.

    ``more_time`` and ``undecided`` are legitimate answers and are recorded exactly like
    any other. Nothing here treats either as a failure to engage.
    """
    if body.criterion_id is not None:
        owned_criterion(store, account_id, body.criterion_id)
    try:
        decision_id = store.record_decision(
            account_id, choice=body.choice, action_text=body.action_text,
            reflection_id=body.reflection_id, pattern_id=body.pattern_id,
            criterion_id=body.criterion_id, revisit_on=body.revisit_on,
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))

    postponements = store.count_postponements(account_id, criterion_id=body.criterion_id)
    return {
        "decision_id": decision_id,
        "choice": body.choice,
        "postponements_on_this_concern": postponements,
        # The front end uses this to know the signature question is now available. It is
        # a fact about the record, never a nudge — waiting is a legitimate decision.
        "probe_available": store.should_probe_postponement(
            account_id, criterion_id=body.criterion_id
        ),
    }


# ---------------------------------------------------------------- my progress

@router.get("/progress")
def progress(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """The longitudinal view.

    Criteria against observed experience, recurring unmet needs, decisions repeatedly
    postponed, changes in stated priorities, and the actions the user chose.

    **No score of any kind.** This counts and compares; it does not rate. There is
    deliberately no aggregate number here, and none that could be mistaken for one.
    """
    criteria = store.list_criteria(account_id, status="all")
    active = [c for c in criteria if c["status"] == "active"]
    decisions = store.list_decisions(account_id)
    patterns = store.list_patterns(account_id, status="all")

    # Criteria whose standard has been revised — "changes in personal priorities".
    revised = []
    for c in active:
        if c["version"] > 1:
            revised.append({
                "criterion_id": c["id"],
                "value": c["value"],
                "versions": store.criterion_history(account_id, c["lineage_id"]),
            })

    postponed = {}
    for d in decisions:
        if d["choice"] == "more_time" and d["criterion_id"]:
            key = d["criterion_id"]
            postponed.setdefault(key, {"criterion_id": key,
                                       "value": d.get("criterion_value"), "count": 0})
            postponed[key]["count"] += 1

    by_choice: dict[str, int] = {}
    for d in decisions:
        by_choice[d["choice"]] = by_choice.get(d["choice"], 0) + 1

    return {
        "active_criteria": len(active),
        "entries": len(store.list_entries(account_id, limit=10_000)),
        "recent_entries": store.list_entries(account_id, limit=5),
        "open_patterns": [p for p in patterns if p["status"] == "open"],
        "insufficient_evidence": [p for p in patterns
                                  if p["evidence_strength"] == "insufficient"],
        "repeatedly_postponed": sorted(postponed.values(), key=lambda r: -r["count"]),
        "changed_priorities": revised,
        "decisions_by_choice": by_choice,
        "recent_decisions": decisions[:10],
        "unanswered_questions": store.list_interrogations(account_id,
                                                          unanswered_only=True),
        "pending_proposals": store.list_pending_proposals(account_id),
        # What the user keeps writing about, whether or not they ever made it a
        # criterion. Counts and dates only — the same no-score rule as everything else
        # on this screen.
        "themes": _theme_rows(store.theme_trends(account_id)),
    }


def _theme_rows(trends: list[dict]) -> list[dict]:
    """Attach the human label and the sensitivity flag to each counted theme.

    ``sensitive`` travels with the row so a client can decide not to put
    "Sexual consideration" in a notification preview or a shoulder-surfable summary.
    It never governs whether the theme was recognised — only how it is shown.
    """
    from ..themes import is_sensitive, label

    out = []
    for row in trends:
        try:
            out.append({**row, "label": label(row["theme_id"]),
                        "sensitive": is_sensitive(row["theme_id"])})
        except KeyError:
            # An id that has left the vocabulary. Surfaced rather than hidden, because
            # silently dropping it would make the counts quietly wrong.
            out.append({**row, "label": f"(retired theme: {row['theme_id']})",
                        "sensitive": True})
    return out


@router.get("/themes")
def themes(
    person_id: int | None = None,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """What this account's entries have been about, optionally for one person.

    The vocabulary ships with the app, so it is returned alongside the counts: a theme
    with zero entries is meaningful information ("you have never written about this")
    and a client cannot construct it from the counts alone.
    """
    from ..themes import load

    counted = {r["theme_id"]: r for r in store.theme_trends(account_id,
                                                            person_id=person_id)}
    return {
        "themes": [
            {
                "theme_id": tid,
                "label": t["label"],
                "about": t["about"],
                "sensitive": bool(t.get("sensitive")),
                "entries": counted.get(tid, {}).get("entries", 0),
                "first_seen": counted.get(tid, {}).get("first_seen"),
                "last_seen": counted.get(tid, {}).get("last_seen"),
            }
            for tid, t in load().items()
        ],
        "person_id": person_id,
    }
