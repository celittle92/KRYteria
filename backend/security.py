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


#: Words a recovery code is built from. Deliberately short, unambiguous, and easy to
#: copy by hand off a screen onto paper — which is the only place a recovery code is
#: any use. No letters that can be confused when handwritten.
_RECOVERY_WORDS = (
    "anchor amber basil birch cable candle cedar cinder clover cobalt copper coral "
    "cotton crane dahlia delta denim ember fable fennel ferry flint forge garnet "
    "ginger granite harbor hazel indigo ivory jasper juniper kettle lantern laurel "
    "ledger linen lumber maple marble meadow mellow mirror mosaic nickel nutmeg "
    "olive onyx orchid osprey pebble pepper pewter pigment pine plaza quarry quartz "
    "quill raven ribbon rosemary rustic saffron sage sailor silver slate sorrel "
    "spruce sterling summit sycamore tallow tandem teal thimble thistle timber "
    "topaz trellis tundra umber valley velvet vessel walnut willow window winter "
    "wren yarrow zephyr zinc"
).split()

RECOVERY_WORD_COUNT = 6


def generate_recovery_code() -> str:
    """A six-word code, about 39 bits of entropy from a 91-word list.

    Words rather than a hex string because this is written on paper by a person who is
    reading it off a screen once. ``harbor-quartz-willow-ember-slate-nutmeg`` survives
    that trip; ``f3a9c1...`` does not.

    Six words from this list is weaker than a passphrase against an offline attack on a
    stolen database, which is why it is hashed with Argon2id exactly like one. Against
    online guessing it is far beyond reach.
    """
    import secrets

    return "-".join(secrets.choice(_RECOVERY_WORDS)
                    for _ in range(RECOVERY_WORD_COUNT))


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code.

    Not ``hash_passphrase``: that enforces a minimum length meant for human-chosen
    secrets, and rejecting a generated code for being too short would be absurd. Same
    Argon2id hasher, because a recovery code can reset a passphrase and therefore opens
    the journal — it is a credential, not a hint.
    """
    return _hasher.hash(code)


def verify_recovery_code(code: str, stored_hash: str | None) -> bool:
    """Constant-time verify, and still does the work when there is no stored hash."""
    try:
        return _hasher.verify((code or "").strip().lower(),
                              stored_hash or _DUMMY_HASH) and stored_hash is not None
    except Exception:
        return False


def verify_passphrase(passphrase: str, stored_hash: str | None) -> bool:
    """Constant-time verify. ``None`` means 'no such account' — still does the work."""
    try:
        return _hasher.verify(passphrase or "", stored_hash or _DUMMY_HASH) and (
            stored_hash is not None
        )
    except Exception:
        return False
