"""Anonymous accounts, sign in, sign out, preferences."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

from .. import throttle
from ..security import WeakPassphrase
from ..store import Store, StoreError
from .deps import (
    clear_session, current_account, current_account_id, get_store, issue_session,
)
from .schemas import Preferences, SignIn, SignUp

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def sign_up(body: SignUp, response: Response, store: Store = Depends(get_store)):
    """Create an anonymous account.

    No email is collected and none is needed. The handle is whatever the user types.

    Returns a **recovery code**, once. It is the only way back into an account whose
    passphrase is lost, because there is no email to send a reset to — that absence is
    the thing that keeps the account anonymous, and this is what stops it also meaning
    that a forgotten passphrase destroys months of somebody's writing.

    The plaintext exists in this response and nowhere else. It is not stored, cannot be
    re-sent, and is not recoverable from the database.
    """
    # Throttled per handle, like sign-in and recovery. `throttle.py` always said it
    # covered sign-up and this route did not call it — which left the one endpoint that
    # runs Argon2id unconditionally as the cheapest way to make the app do expensive
    # work, and made "that handle is taken" an unmetered existence oracle.
    try:
        throttle.check(body.handle)
    except throttle.TooManyAttempts as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e),
                            headers={"Retry-After": str(e.retry_after)})
    try:
        account_id = store.create_account(body.handle, body.passphrase)
    except WeakPassphrase as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    except sqlite3.IntegrityError:
        throttle.record_failure(body.handle)
        raise HTTPException(status.HTTP_409_CONFLICT, "That handle is taken.")
    throttle.record_success(body.handle)
    recovery_code = store.issue_recovery_code(account_id)
    issue_session(response, account_id)
    return {**store.get_account(account_id), "recovery_code": recovery_code}


@router.post("/recover")
def recover(body: dict, response: Response, store: Store = Depends(get_store)):
    """Set a new passphrase using a recovery code, and sign in.

    Deliberately returns the same 404 for a wrong code, an unknown handle, and an
    account that never had a code. Distinguishing them would answer "does this person
    have an account here", which is the disclosure this whole application refuses.

    The used code is consumed and a fresh one is returned, once. A recovery code that
    kept working after a reset would be a second standing password on the account, on a
    piece of paper the user has already had out.
    """
    handle = str(body.get("handle", "")).strip()
    code = str(body.get("recovery_code", "")).strip().lower()
    new_passphrase = str(body.get("passphrase", ""))

    try:
        throttle.check(handle)
    except throttle.TooManyAttempts as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e),
                            headers={"Retry-After": str(e.retry_after)})

    try:
        account_id = store.reset_passphrase_with_code(handle, code, new_passphrase)
    except WeakPassphrase as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    if account_id is None:
        throttle.record_failure(handle)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "That handle and recovery code do not match an account.",
        )

    throttle.record_success(handle)
    fresh_code = store.issue_recovery_code(account_id)
    issue_session(response, account_id)
    return {**store.get_account(account_id), "recovery_code": fresh_code}


@router.post("/signin")
def sign_in(body: SignIn, response: Response, store: Store = Depends(get_store)):
    # Throttled per handle. See backend/throttle.py for why it is not per IP.
    try:
        throttle.check(body.handle)
    except throttle.TooManyAttempts as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e),
                            headers={"Retry-After": str(e.retry_after)})
    account_id = store.verify_account(body.handle, body.passphrase)
    if account_id is None:
        throttle.record_failure(body.handle)
        # One message for both cases, so the response does not reveal which handles exist.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Handle or passphrase is wrong.")
    throttle.record_success(body.handle)
    issue_session(response, account_id)
    return store.get_account(account_id)


@router.post("/signout")
def sign_out(response: Response):
    clear_session(response)
    return {"signed_out": True}


@router.get("/me")
def me(account: dict = Depends(current_account)):
    """Never includes the passphrase hash — ``get_account`` does not select it."""
    return account


@router.patch("/preferences")
def set_preferences(
    body: Preferences,
    account_id: int = Depends(current_account_id),
    store: Store = Depends(get_store),
):
    try:
        store.set_preferences(
            account_id, tone_mode=body.tone_mode, theme=body.theme,
            resource_offering=body.resource_offering, retention=body.retention,
            region=body.region,
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return store.get_account(account_id)
