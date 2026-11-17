"""Refuse an interpreter too old to run the application, with the fix in the message.

WHY THIS EXISTS. macOS ships Python 3.9 as ``python3`` through the Command Line Tools,
and the README's first instruction is ``python3 -m venv .venv``. On such a machine that
builds a 3.9 environment, and the failure that follows arrives late and unhelpfully — a
pip resolver error naming a transitive dependency, or a ``TypeError: unsupported operand
type(s) for |`` from inside a library. Neither says what is actually wrong. The teaching
staff get ten minutes to run this from a fresh clone, and a confusing error spends all
of them.

WHY IT IS NOT IN ``backend/__init__.py``. It was, briefly, and that was wrong: it broke
``tests/test_offline.py``, which runs the store layer on the system interpreter with
nothing installed, and does so deliberately. The precise claim is **the store layer runs
on 3.9; the application does not.** So the guard sits on the application's entry points
— the server and the seeders — and the package stays importable wherever it can be.

WHY THE SYNTAX IS OLD. No ``X | None``, no dataclasses, no walrus. A guard the
interpreter cannot parse is not a guard. Every other module here opens with
``from __future__ import annotations``, so they parse on 3.9 and fail later and worse,
which is the whole situation this prevents.
"""

import sys

MINIMUM = (3, 12)

_MESSAGE = """
KRYteria needs Python {needed} or newer, and this is Python {running}.
  ({executable})

macOS ships 3.9 as `python3`, so this is usually a virtual environment built with the
wrong interpreter rather than a missing install.

Find a newer one:
    ls /opt/homebrew/bin/python3.1* /usr/local/bin/python3.1* 2>/dev/null
    brew install python@3.12        # if there is none

Then rebuild the environment with it:
    rm -rf .venv
    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python -m backend.seed_demo
    .venv/bin/python -m uvicorn backend.main:app --port 8000

Or skip Python entirely — the Dockerfile pins the interpreter:
    docker build -t kryteria . && docker run -p 8000:8000 kryteria

Or just open the hosted copy: https://kryteria.onrender.com
"""


def require(minimum=MINIMUM):
    """Exit with an actionable message when the interpreter is too old."""
    if sys.version_info >= minimum:
        return
    raise SystemExit(_MESSAGE.format(
        needed=".".join(str(n) for n in minimum),
        running=".".join(str(n) for n in sys.version_info[:3]),
        executable=sys.executable,
    ))
