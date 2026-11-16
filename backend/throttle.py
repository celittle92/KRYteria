"""Brute-force protection for the credential endpoints.

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


def reset() -> None:
    """Drop all state. For tests."""
    with _lock:
        _attempts.clear()
        _tripped.clear()
