"""The theme vocabulary: what a Brain Dump was *about*.

Christine, 2026-11-11: *"The user doesn't have to explicitly say, 'I would like to discuss
emotional intimacy now.' They can write a messy paragraph about what happened last night,
and the agent can recognize that the relevant topic is emotional vulnerability, not
punctuality."*

Themes sit deliberately beside the existing axes rather than inside any of them:

  * **Not criteria.** A criterion is the user's own standard, created by them and assessed
    against evidence. A theme is a topic label on an entry. The agent may recognise
    *reciprocity and initiative* in an entry from somebody who has never created a
    reciprocity criterion — which is the point, because it is how the app notices what a
    person keeps writing about before they have named it.
  * **Not observation kinds.** Those say what a sentence *is* (event, interpretation…).
    A theme says what the entry is *about*. One entry carries several.
  * **Not evidence relations.** Those connect an observation to a criterion.

**The vocabulary is closed, and that is a safeguard rather than a limitation.** A model
free to invent theme labels would produce a different taxonomy every run, and "recurring
theme" over an unstable vocabulary means nothing. ``validate`` rejects an unknown id
instead of storing it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

THEMES_PATH = Path(__file__).resolve().parent.parent / "data" / "themes.json"


class UnknownTheme(ValueError):
    """A theme id outside the curated vocabulary."""


@lru_cache(maxsize=1)
def load() -> dict[str, dict[str, Any]]:
    """The vocabulary, keyed by id."""
    if not THEMES_PATH.is_file():
        raise FileNotFoundError(f"Theme vocabulary missing: {THEMES_PATH}")
    blob = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    themes = {t["id"]: t for t in blob["themes"]}
    if len(themes) != len(blob["themes"]):
        raise ValueError("Duplicate theme id in the vocabulary.")
    return themes


def ids() -> list[str]:
    return list(load())


def label(theme_id: str) -> str:
    return load()[theme_id]["label"]


def is_sensitive(theme_id: str) -> bool:
    """Drives presentation only — never whether the theme is recognised.

    A sensitive theme must not appear in a notification preview or any surface the user
    did not open deliberately. *"Your reflection about Adrian's sexual boundaries is
    ready"* is the failure this flag exists to prevent.
    """
    return bool(load()[theme_id].get("sensitive"))


def validate(theme_ids: list[str]) -> list[str]:
    """Return the ids, de-duplicated and in vocabulary order, or raise."""
    known = load()
    unknown = [t for t in theme_ids if t not in known]
    if unknown:
        raise UnknownTheme(
            f"Unknown theme id(s): {unknown}. The vocabulary is closed on purpose — a "
            f"model inventing labels makes 'recurring theme' meaningless. Known ids: "
            f"{', '.join(known)}. Add one to data/themes.json deliberately."
        )
    seen = set(theme_ids)
    return [t for t in known if t in seen]


def prompt_block() -> str:
    """The vocabulary, rendered for a runtime prompt.

    Built from the data file rather than written into the prompt by hand, so the two
    cannot drift — a theme added to the vocabulary is one the agent is told about.
    """
    lines = []
    for t in load().values():
        lines.append(f"- **`{t['id']}`** — {t['label']}. {t['about']}")
        if t.get("sounds_like"):
            examples = " · ".join(f'"{s}"' for s in t["sounds_like"][:3])
            lines.append(f"    Sounds like: {examples}")
        if t.get("not_this"):
            lines.append(f"    Careful: {t['not_this']}")
    return "\n".join(lines)
