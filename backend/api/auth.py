"""Anonymous accounts, sign in, sign out, preferences."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

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
    """
    try:
        account_id = store.create_account(body.handle, body.passphrase)
    except WeakPassphrase as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "That handle is taken.")
    issue_session(response, account_id)
    return store.get_account(account_id)


@router.post("/signin")
def sign_in(body: SignIn, response: Response, store: Store = Depends(get_store)):
    account_id = store.verify_account(body.handle, body.passphrase)
    if account_id is None:
        # One message for both cases, so the response does not reveal which handles exist.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Handle or passphrase is wrong.")
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
