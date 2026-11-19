"""Brute-force protection for the credential endpoints, and a bound on account creation.

Two limiters live here and they are different shapes. The first is keyed on the handle
being attempted and guards *access* to an account that exists. The second has no key at
all and guards the *creation* of new ones, because a per-handle counter cannot see a
script that never reuses a handle. Its reasoning is at the bottom of this file.


KRYteria had none. Sign-in, sign-up and recovery could all be called as fast as the
network allowed, which on a hosted app with handle-and-passphrase auth is the gap that
matters most: a handle is short, guessable, and in the demo's case published.

Keyed by handle, deliberately — not by IP
-----------------------------------------
The usual answer is per-IP rate limiting. This application cannot do that without giving
up something it has promised twice over: ``accounts.region`` is user-set and never
inferred, and ``test_location_is_never_inferred_from_the_request`` walks the AST of every
route module to prove nothing touches the request except its cookies. An IP address is a
location, and the whole posture here is that the app holds as little as possible about
where somebody is.

So the counter is keyed on the handle being attempted. That covers the attack this
design is actually exposed to — somebody working through passphrases against a known
handle — without the app ever learning anything about who is asking.

It does not cover spraying one passphrase across many handles. That trade is deliberate
and stated rather than hidden: closing it would mean identifying the caller, and this is
not an app that should.

A locked handle is never a locked account
-----------------------------------------
Lockout is a denial-of-service primitive: anyone who knows a handle could otherwise keep
its owner out. So the window is short, it clears on success, and it never disables the
account — it only asks the caller to wait.

In-memory on purpose: one process, and a counter that evaporates on restart is the right
failure mode for something whose job is to slow an attacker down rather than to keep
books on anybody.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

#: Attempts allowed per handle inside the window before refusing.
MAX_ATTEMPTS = 8

#: Rolling window, seconds. Short enough that a real person who mistyped their
#: passphrase a few times is not locked out of their own journal for the evening.
WINDOW_SECONDS = 300

#: How long to refuse once tripped.
COOLDOWN_SECONDS = 300

_attempts: dict[str, deque[float]] = {}
_tripped: dict[str, float] = {}
_lock = Lock()


class TooManyAttempts(Exception):
    """Raised when a handle has been tried too often. Carries the seconds to wait."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Too many attempts. Try again in {retry_after} seconds.")
        self.retry_after = retry_after


def _key(handle: str) -> str:
    return (handle or "").strip().lower()


def check(handle: str, *, now: float | None = None) -> None:
    """Raise ``TooManyAttempts`` if this handle is in cooldown. Call before verifying."""
    now = time.time() if now is None else now
    k = _key(handle)
    with _lock:
        until = _tripped.get(k)
        if until is not None:
            if now < until:
                raise TooManyAttempts(int(until - now) + 1)
            del _tripped[k]
            _attempts.pop(k, None)


def record_failure(handle: str, *, now: float | None = None) -> None:
    """Count a failed attempt, and trip the cooldown once there are too many."""
    now = time.time() if now is None else now
    k = _key(handle)
    with _lock:
        q = _attempts.setdefault(k, deque())
        q.append(now)
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        if len(q) >= MAX_ATTEMPTS:
            _tripped[k] = now + COOLDOWN_SECONDS
            q.clear()


def record_success(handle: str) -> None:
    """Clear the record. Somebody who got in was not the attacker being slowed down."""
    k = _key(handle)
    with _lock:
        _attempts.pop(k, None)
        _tripped.pop(k, None)


# ---------------------------------------------------------------- new accounts
#
# Everything above is keyed on a handle, and a *successful* sign-up clears its key. A
# script posting a fresh handle each time was therefore never slowed down at all, and
# unlimited account creation is a lever on the one resource this app actually spends:
#
#   120,000 tokens per account per day, 2,000,000 globally. Seventeen new accounts
#   exhaust the global cap, and then KRYteria analyses nothing for anybody — including
#   whoever is marking it — until midnight UTC.
#
# The money was never the exposure. The global cap counts input and output together, so
# even at output prices the worst day costs about a dollar; that cap does its job. What
# it does not do is stop one stranger spending everybody else's share.
#
# So this counter has no key. It bounds how fast the application as a whole will create
# accounts, which is the only thing that can be bounded without asking who is calling —
# the same constraint that put the per-handle counter above on a handle instead of an IP.
#
# The trade, stated rather than buried: a limiter with no key is itself a denial-of-
# service primitive. Somebody burning the hourly allowance blocks genuine sign-ups for an
# hour. That is accepted because the blast radius is small and the alternative is worse:
#
#   * The whole demo needs no account. Nine characters open in one click, so a visitor
#     who meets this limit can still see everything the app does.
#   * Existing accounts are untouched. Sign-in, journals and analysis carry on; this
#     refuses creation, never access.
#   * The failure it prevents takes analysis away from everyone at once, which is both
#     worse and much harder to notice than a sign-up form saying "try again shortly".
#
# Two windows rather than one. The hourly limit stops a burst; the daily limit stops a
# patient script trickling under it, which is the attack an hourly-only bound invites.

#: New accounts the whole application will create per hour, and per day.
#:
#: Sized against expected honest use rather than against the attack: this is a class
#: project whose hosted instance sees a handful of real sign-ups a day. A limit that
#: never inconveniences a genuine visitor and still forces an attacker to take two days
#: over what took two minutes is the right shape.
MAX_NEW_ACCOUNTS_PER_HOUR = 12
MAX_NEW_ACCOUNTS_PER_DAY = 40

_HOUR = 3600
_DAY = 86400

_new_accounts: deque[float] = deque()


def check_new_account(*, now: float | None = None) -> None:
    """Raise ``TooManyAttempts`` if the app has created too many accounts lately.

    Call **before** hashing: Argon2id is deliberately expensive, and an endpoint that
    does the work and then refuses has paid for the attack anyway.
    """
    now = time.time() if now is None else now
    with _lock:
        _prune(now)
        in_hour = sum(1 for t in _new_accounts if now - t <= _HOUR)
        if in_hour >= MAX_NEW_ACCOUNTS_PER_HOUR:
            oldest = min(t for t in _new_accounts if now - t <= _HOUR)
            raise TooManyAttempts(int(_HOUR - (now - oldest)) + 1)
        if len(_new_accounts) >= MAX_NEW_ACCOUNTS_PER_DAY:
            raise TooManyAttempts(int(_DAY - (now - _new_accounts[0])) + 1)


def record_new_account(*, now: float | None = None) -> None:
    """Count an account that was actually created.

    Only successes count. A sign-up refused because the handle is taken created nothing,
    and letting 409s fill this counter would hand an attacker a way to close the door on
    everybody without opening it once. Repeated attempts on one handle are already the
    per-handle counter's job.
    """
    now = time.time() if now is None else now
    with _lock:
        _prune(now)
        _new_accounts.append(now)


def _prune(now: float) -> None:
    """Drop anything older than a day. Caller holds the lock."""
    while _new_accounts and now - _new_accounts[0] > _DAY:
        _new_accounts.popleft()


def reset_new_accounts() -> None:
    """Drop only the creation counter, leaving the per-handle counters alone.

    For test fixtures that need an authenticated client and are not about this limit. A
    suite builds dozens of accounts in a second, which is exactly the shape this bound
    exists to refuse, so without a way to stand it down every unrelated test would be
    gated on a rate limiter. Narrow on purpose: a fixture that cleared *all* throttle
    state would silently disarm the brute-force tests too.
    """
    with _lock:
        _new_accounts.clear()


def reset() -> None:
    """Drop all state. For tests."""
    with _lock:
        _attempts.clear()
        _tripped.clear()
        _new_accounts.clear()
