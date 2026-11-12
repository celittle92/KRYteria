"""Account-level routes: usage and cost, support resources, export, deletion, demo data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from .. import costs
from ..store import Store, StoreError
from .deps import clear_session, current_account_id, get_provider, get_store
from .schemas import DeleteAccount, ResourceOfferResponse

router = APIRouter(prefix="/api", tags=["account"])


# ---------------------------------------------------------------- tokenomics

@router.get("/usage")
def usage(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """What this account has spent today, and what the app knows about pricing.

    ``cost_available`` is false when ``data/prices.json`` has no entry for the model. The
    app then reports cost as *unavailable* rather than printing 0.00 as though runs were
    free — an invented zero is worse than an absent figure.
    """
    _, info = get_provider()
    today = store.usage_today(account_id)
    priced = costs.have_prices_for(info.model_name)
    return {
        "today": today,
        "model": info.model_name,
        "mode": info.mode.value,
        "simulated": info.simulated,
        "cost_available": priced,
        "note": (
            "Demo mode: nothing here is billed and simulated usage is excluded from "
            "every figure." if info.simulated else
            None if priced else
            "No published prices are loaded for this model, so cost cannot be reported."
        ),
    }


@router.get("/usage/projection")
def projection(
    runs_per_user_per_month: int = 12,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Scale projections for the report, with the assumptions returned alongside.

    Measured from this account's real runs. With no billable runs yet it says so rather
    than projecting from a guess.
    """
    _, info = get_provider()
    today = store.usage_today(account_id)
    if not today["calls"] or info.simulated:
        return {
            "available": False,
            "reason": ("No billable runs recorded yet — demo and test usage are excluded "
                       "from cost figures by design."),
        }
    cost_per_run = today["cost_usd"] / today["calls"]
    return {
        "available": True,
        "measured_from": {"calls": today["calls"], "cost_usd": today["cost_usd"]},
        "at_100_users": costs.project_monthly(cost_per_run, runs_per_user_per_month, 100),
        "at_10000_users": costs.project_monthly(cost_per_run, runs_per_user_per_month,
                                                10_000),
    }


# ---------------------------------------------------------------- safety resources

#: Carried on every resources response, whatever the directory holds.
#:
#: The one piece of safety information KRYteria can state without the risk of being
#: stale, because it does not depend on our data being current — she knows her own
#: emergency number better than this app does. Verifying six countries on 2026-11-12
#: found two dead government pages, one organisation's site down, and one organisation
#: contradicting itself about its own number. Against that, the honest fallback has to
#: be something no file of ours can get wrong.
EMERGENCY_NOTE = (
    "If you are in immediate danger, call your local emergency number."
)

#: Shown beside the dated entries. A number with a date on it can be judged; a bare
#: number asks to be trusted.
STALENESS_NOTE = (
    "Each entry shows when KRYteria last checked it against the organisation's own "
    "page. Numbers and opening hours do change, and services close."
)


@router.get("/resources")
def list_resources(
    category: str | None = None,
    region: str | None = None,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """The curated directory, available on request at any time.

    Declining an offer stops the app volunteering resources; it never stops the user
    asking for them. This route is always open.

    ``region`` falls back to the account's own setting, and to global services if she
    has not said. **It is never inferred from the request** — no IP lookup, no
    `X-Forwarded-For`, no timezone guess. For somebody whose device may be monitored,
    silently working out where they are is the wrong instinct; and a country guessed
    from an IP is wrong often enough that acting on it in a crisis is worse than saying
    we do not know.
    """
    account = store.get_account(account_id) or {}
    asked = (region or account.get("region") or "").strip().upper() or None
    rows = store.list_resources(region=asked, category=category)
    return {
        "region": asked,
        "region_source": ("query" if region else
                          "account" if account.get("region") else "unset"),
        "resources": rows,
        # Always present, never conditional on the directory having anything.
        "emergency_note": EMERGENCY_NOTE,
        "staleness_note": STALENESS_NOTE if rows else None,
        # An empty directory is a truthful answer and must read as one. The alternative
        # — quietly serving US numbers to everybody — is the bug this replaced.
        "note": (
            None if rows else
            ("KRYteria has no checked resource for that yet, and will not invent one. "
             + ("Setting your country in Settings may find local services."
                if not asked else
                "If you know a service that belongs here, it can be added once somebody "
                "has verified it against the organisation's own site."))
        ),
    }


@router.post("/resource-offers/{offer_id}/respond")
def respond_to_offer(
    offer_id: int,
    body: ResourceOfferResponse,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Record what the user said about an offer of support.

    A decline is honoured, not argued with: the app stops raising resources at that level
    and below. It does **not** turn the safety layer off — a new disclosure of immediate
    danger still surfaces emergency options.
    """
    try:
        store.respond_to_offer(account_id, offer_id, body.response)
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return {
        "offer_id": offer_id,
        "response": body.response,
        "note": ("Understood — I won't bring those up again unless you ask, or something "
                 "changes that makes immediate safety relevant."
                 if body.response == "declined" else None),
    }


@router.get("/safety-events")
def safety_events(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """The user's own safety log. Theirs to read, like everything else here."""
    return store.list_safety_events(account_id)


# ---------------------------------------------------------------- data control

@router.get("/export")
def export(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Everything the user put in, as JSON.

    Omits the passphrase hash, which must never leave the database.
    """
    return store.export_account(account_id)


@router.post("/account/delete")
def delete_account(
    body: DeleteAccount,
    response: Response,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Delete everything. Rows are removed, not flagged.

    Asks for the passphrase and a typed confirmation because it cannot be undone — and
    because a journal like this is exactly the kind of data somebody might be deleting
    under pressure from another person, so a stray click should not do it.
    """
    account = store.get_account(account_id)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is not valid.")
    if store.verify_account(account["handle"], body.passphrase) != account_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Passphrase is wrong.")
    store.delete_account(account_id)
    clear_session(response)
    return {"deleted": True,
            "note": "Everything has been removed. This cannot be undone."}


# ---------------------------------------------------------------- demo

@router.post("/demo/reset")
def reset_demo(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    """Rebuild the synthetic demo account from scratch.

    Refuses on a real account. Synthetic content is never mixed with real records, and
    the one-click reset must not be a one-click way to erase somebody's journal.
    """
    from ..seed_demo import DEMO_HANDLE, seed

    account = store.get_account(account_id)
    if not account or not account["is_demo"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This is a real account, not the demo. Reset only works on the demo account.",
        )
    seed(store, reset=True)
    return {"reset": True, "handle": DEMO_HANDLE}
