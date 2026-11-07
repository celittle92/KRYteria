"""Passphrase hashing. Argon2id via pwdlib, per the semester rule in AGENT.MD.

The library generates its own random salt per passphrase and embeds it in the hash string,
so nothing here adds one on top. Verification goes through the library's own constant-time
compare — never ``==``.

Nothing in this module returns, logs, or renders a passphrase or a hash.
"""

from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_hasher = PasswordHash((Argon2Hasher(),))

#: A throwaway hash of a random value, used to spend comparable work when the handle does
#: not exist — so response time does not tell an attacker which handles are real.
_DUMMY_HASH = _hasher.hash("kryteria-timing-equaliser")

MIN_PASSPHRASE_LENGTH = 10


class WeakPassphrase(ValueError):
    pass


def hash_passphrase(passphrase: str) -> str:
    if len(passphrase or "") < MIN_PASSPHRASE_LENGTH:
        raise WeakPassphrase(
            f"Use at least {MIN_PASSPHRASE_LENGTH} characters. A few ordinary words in a "
            "row is both stronger and easier to remember than a short scramble."
        )
    return _hasher.hash(passphrase)


def verify_passphrase(passphrase: str, stored_hash: str | None) -> bool:
    """Constant-time verify. ``None`` means 'no such account' — still does the work."""
    try:
        return _hasher.verify(passphrase or "", stored_hash or _DUMMY_HASH) and (
            stored_hash is not None
        )
    except Exception:
        return False
