"""Shared dependencies: the store, the model provider, and the current account.

**No route in this application takes an account id as a parameter.** The account is
resolved from a signed session cookie and nothing else, which is what makes user-level
data isolation a property of the plumbing rather than something each route has to remember
to check. A route that wanted to read somebody else's rows would have to be rewritten to
do it.

Rows belonging to another account return **404, not 403**. Telling somebody "that exists
but is not yours" confirms it exists, which is information they are not entitled to.
"""

from __future__ import annotations

import os
import secrets
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..provider import ProviderInfo, build
from ..store import Store

SESSION_COOKIE = "kryteria_session"
SESSION_SALT = "kryteria-session-v1"

#: How long a session is good for, enforced on the SERVER when the cookie is read.
#:
#: This was a URLSafeSerializer with a 30-day ``max_age`` on set_cookie, which is a
#: different and much weaker thing: ``max_age`` is an instruction to the browser about
#: when to stop sending the cookie, not a statement about when the token stops being
#: valid. A copied cookie value worked forever — past the 30 days, and past signing
#: out, because sign-out deletes the browser's copy and nothing else. For an app
#: holding this kind of writing, a session token with no expiry is the wrong default.
SESSION_MAX_AGE = 60 * 60 * 24 * 14


@lru_cache(maxsize=1)
def _serializer() -> URLSafeTimedSerializer:
    """Signs the session cookie.

    A generated key in development means sessions do not survive a restart, which is
    correct for a laptop and wrong for a deployment — set ``KRYTERIA_SECRET_KEY`` there.
    Generating one silently in production would log everybody out on every deploy.
    """
    key = os.getenv("KRYTERIA_SECRET_KEY") or secrets.token_urlsafe(32)
    return URLSafeTimedSerializer(key, salt=SESSION_SALT)


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store(os.getenv("KRYTERIA_DB_PATH") or None)


@lru_cache(maxsize=1)
def get_provider() -> tuple[object, ProviderInfo]:
    return build()


def issue_session(response: Response, account_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        _serializer().dumps({"account_id": account_id}),
        httponly=True,          # the browser's JS cannot read it
        samesite="lax",
        secure=os.getenv("KRYTERIA_SECURE_COOKIES", "").lower() == "true",
        max_age=SESSION_MAX_AGE,
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_account_id(request: Request) -> int:
    """The only way a route learns whose data it is looking at."""
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    try:
        payload = _serializer().loads(raw, max_age=SESSION_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Session has expired. Please sign in again.")
    except BadSignature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is not valid.")
    account_id = payload.get("account_id")
    if not isinstance(account_id, int):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is not valid.")
    return account_id


def current_account(
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
) -> dict:
    account = store.get_account(account_id)
    if account is None:
        # The account was deleted while the cookie was still live.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is not valid.")
    return account


# ---------------------------------------------------------------- ownership guards
#
# Every one of these answers "is this row this account's?" and raises 404 if not. They
# exist so a route handler cannot forget; the alternative is remembering to filter by
# account_id in thirty places and getting it right every time.


def owned_profile(store: Store, account_id: int, profile_id: int) -> dict:
    for p in store.list_profiles(account_id, include_archived=True):
        if p["id"] == profile_id:
            return p
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No such profile.")


def owned_criterion(store: Store, account_id: int, criterion_id: int) -> dict:
    for c in store.list_criteria(account_id, status="all"):
        if c["id"] == criterion_id:
            return c
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No such criterion.")


def owned_person(store: Store, account_id: int, person_id: int) -> dict:
    for p in store.list_people(account_id):
        if p["id"] == person_id:
            return p
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No such person.")


def owned_entry(store: Store, account_id: int, entry_id: int) -> dict:
    entry = store.get_entry(account_id, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such entry.")
    return entry


def resolve_domain(store: Store, account_id: int, domain_id: int | None,
                   profile: dict | None = None) -> int:
    """Find the domain for an entry, creating a default if the user has none.

    The calendar is optional and so is domain management — somebody should be able to
    write their first journal entry without having configured anything first.
    """
    domains = store.list_domains(account_id)
    if domain_id is not None:
        if not any(d["id"] == domain_id for d in domains):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such domain.")
        return domain_id
    if profile and profile.get("domain_id"):
        return profile["domain_id"]
    if domains:
        return domains[0]["id"]
    return store.create_domain(account_id, "Dating", "romantic")
