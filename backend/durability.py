"""Whether this deployment's database survives a restart — and saying so out loud.

The free hosting tier KRYteria runs on has an **ephemeral filesystem**: the SQLite file
is rebuilt on every restart and every deploy. That fact was written down in three places
— ``render.yaml``, the ``Dockerfile`` and ``README.md`` — and said to nobody who mattered.
A person signing up on the hosted site was told nothing at all, which means the app was
quietly accepting a relationship journal it knew it could not keep.

That is the same failure the rest of this project is built to avoid. ``docs/privacy.md``
refuses to promise that the model provider forgets anything, because nobody has it in
writing. ``data/resources_international.json`` is deliberately empty rather than filled
from memory. Durability is the same kind of claim, and an app that takes somebody's
writing without mentioning it is making the claim by omission.

**The default is the hosted case, not the laptop case.** A container's filesystem is
ephemeral unless an operator mounts a disk and says so, which is why the ``Dockerfile``
sets this to ``false`` — deployed is the situation where being wrong does damage. A direct
``uvicorn`` run on somebody's own machine is a real disk and is treated as durable, the
same way ``KRYTERIA_SEED_ON_BOOT`` is off locally and on in the container.

Nothing here blocks a sign-up. A person may well want a disposable journal, and deciding
for her is not this product's habit — the rule is that she is told before she writes, and
that export is one click away on the same screen.
"""

from __future__ import annotations

import os

#: Set to "false" by a deployment whose disk does not survive a restart.
ENV_VAR = "KRYTERIA_STORAGE_DURABLE"

_FALSE = {"0", "false", "no", "off"}
_TRUE = {"1", "true", "yes", "on"}

#: What the UI says when the storage is not durable. One place, so the sign-up screen,
#: the settings screen and ``/api/health`` cannot drift into three different promises.
EPHEMERAL_NOTE = (
    "This instance does not keep anything. It runs on free hosting with a disposable "
    "disk, so every account, entry and criterion is erased whenever the app restarts or "
    "is updated — which can happen at any time, without warning. Use it to try KRYteria, "
    "not to keep a record. Export anything you want to keep."
)

DURABLE_NOTE = (
    "This instance keeps what you write, on a disk that survives restarts. It is still "
    "ordinary SQLite on a server rather than production-grade encrypted storage."
)


def storage_is_durable() -> bool:
    """Does the database survive a restart?

    Unset means a direct run on somebody's own filesystem, which is durable. The
    ``Dockerfile`` sets it to ``false`` so that every containerised deployment has to
    opt *in* to claiming durability, after actually mounting a disk.
    """
    raw = os.getenv(ENV_VAR, "").strip().lower()
    if raw in _FALSE:
        return False
    if raw in _TRUE:
        return True
    return True


def storage_note() -> str:
    return DURABLE_NOTE if storage_is_durable() else EPHEMERAL_NOTE
