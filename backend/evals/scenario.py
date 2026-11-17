"""Build the small world a case needs, run it, and tear it down.

Every case gets its **own account** in a throwaway database. That is not tidiness: the
reasoning cases turn on what the record already contains ("the record shows one late
arrival with notice"), and a case that could see another case's entries would grade
something other than what it claims to. It also means the isolation guarantees the
product rests on are exercised by the harness itself.

A case's ``setup`` block names criteria and prior entries in plain language. Criteria
arrive as names; the agents work in ids; :class:`World` holds the mapping both ways so
the report can speak the names a person wrote.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Prior entries are backdated so "earlier in the record" is true in the data and not
#: only in the prose. Entry order carries meaning for the pattern cases.
_DAY = 86_400

#: EVERY resources file, not just the US one.
#:
#: This was resources_us.json alone, which contains only US rows — and the eval accounts
#: set no region. `list_resources` returns GLOBAL rows only for an account that has not
#: said where it is, and the US file has none, so `resources_to_offer` could never return
#: anything and every "was support offered?" case failed for a reason that has nothing to
#: do with the agents. saf-01 failed exactly that way on the first live reasoning run.
#:
#: The same shape of bug as the one that shipped to production: the default region stopped
#: being "US" and two places that quietly depended on it were never updated.
RESOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def seed_resources(store: Any) -> int:
    """Load the curated resources into the eval database.

    Not optional. Half the safety pack asks whether support was *offered*, and
    ``resources_to_offer`` can only return rows that exist — so an unseeded database
    makes every one of those cases fail for a reason that has nothing to do with the
    agents. The first demo run of this harness failed exactly that way.
    """
    paths = sorted(RESOURCES_DIR.glob("resources_*.json"))
    if not paths:
        raise FileNotFoundError(
            f"No resources_*.json in {RESOURCES_DIR}, and the safety cases cannot be "
            f"graded without them."
        )
    seeded = 0
    for path in paths:
        rows = json.loads(path.read_text(encoding="utf-8")).get("resources", [])
        if rows:
            seeded += len(store.seed_resources(rows))
    if not seeded:
        raise RuntimeError("Resource files loaded but nothing was seeded.")
    return seeded


@dataclass
class World:
    """One case's account, and the ids inside it."""

    account_id: int
    domain_id: int
    profile_id: int
    profile_name: str
    person_id: int | None = None
    criterion_ids: dict[str, int] = field(default_factory=dict)
    entry_ids: list[int] = field(default_factory=list)

    @property
    def names(self) -> dict[int, str]:
        return {v: k for k, v in self.criterion_ids.items()}


def build_world(store: Any, case: dict, *, handle_prefix: str = "eval") -> World:
    """Stand up the account, profile, criteria, person and prior entries for one case."""
    setup = case.get("setup") or {}

    handle = f"{handle_prefix}-{case['id']}-{uuid.uuid4().hex[:8]}"
    account_id = store.create_account(handle, "a long enough eval passphrase")
    # Eval accounts declare a region, because the cases that ask "was support offered?"
    # are testing the offering logic, not the no-region path.
    #
    # Without it they tested the wrong thing and could not pass. An account that has not
    # said where it is sees GLOBAL rows only; the one global row is an emergency number;
    # and resources_to_offer deliberately withholds emergency numbers below
    # immediate_danger, because volunteering 911 for a pattern-level concern overstates
    # what was described. All three of those behaviours are right, and together they mean
    # a region-less account is offered nothing at disclosure level.
    #
    # That combination is a real product gap and is NOT papered over here — it is written
    # up for Christine to decide on. What this line fixes is only the test: the no-region
    # path deserves a case of its own rather than silently breaking every other one.
    store.set_preferences(account_id, region="US")

    domain_id = store.create_domain(account_id, setup.get("domain", "Dating"),
                                    setup.get("domain_kind", "romantic"))

    profile_name = setup.get("profile", "Long-term KRYteria")
    profile_id = store.create_profile(
        account_id, profile_name,
        objective=setup.get("objective"), domain_id=domain_id,
    )

    person_alias = setup.get("person", "The person I'm seeing")
    person_id = store.upsert_person(account_id, person_alias, domain_id=domain_id)

    world = World(account_id=account_id, domain_id=domain_id, profile_id=profile_id,
                  profile_name=profile_name, person_id=person_id)

    # --- criteria ------------------------------------------------------------
    # A case may give a bare name, or a {name, tier, relevance} object when the tier is
    # what the case is actually about (the profile-bleed and not-applicable cases).
    tiers = setup.get("tiers") or {}
    for spec in setup.get("criteria", []):
        if isinstance(spec, str):
            name, tier, relevance = spec, tiers.get(spec, "preferred"), "relevant"
        else:
            name = spec["name"]
            tier = spec.get("tier", tiers.get(name, "preferred"))
            relevance = spec.get("relevance", "relevant")
        criterion_id = store.create_criterion(
            account_id, value=name,
            desired_behavior=(spec.get("desired_behavior")
                              if isinstance(spec, dict) else None)
            or f"Behaviour that demonstrates {name.lower()}.",
        )
        store.add_criterion_to_profile(
            account_id, profile_id, criterion_id, tier=tier, relevance=relevance,
        )
        world.criterion_ids[name] = criterion_id

    # --- a second profile, for the Jimmy G / profile-bleed cases -------------
    other = setup.get("other_profile")
    if other:
        other_id = store.create_profile(account_id, other["name"], domain_id=domain_id)
        for spec in other.get("criteria", []):
            name = spec if isinstance(spec, str) else spec["name"]
            tier = "preferred" if isinstance(spec, str) else spec.get("tier", "preferred")
            relevance = ("relevant" if isinstance(spec, str)
                         else spec.get("relevance", "relevant"))
            criterion_id = world.criterion_ids.get(name) or store.create_criterion(
                account_id, value=name,
                desired_behavior=f"Behaviour that demonstrates {name.lower()}.",
            )
            world.criterion_ids.setdefault(name, criterion_id)
            store.add_criterion_to_profile(
                account_id, other_id, criterion_id, tier=tier, relevance=relevance,
            )

    # --- prior entries -------------------------------------------------------
    now = time.time()
    older = list(setup.get("entries", []))
    for offset, body in enumerate(reversed(older), start=1):
        occurred = time.strftime("%Y-%m-%d", time.gmtime(now - offset * _DAY))
        entry_id = store.create_entry(
            account_id, domain_id, occurred_on=occurred, entry_mode="free",
            body=body, person_id=person_id,
        )
        world.entry_ids.append(entry_id)
    world.entry_ids.reverse()

    return world


def new_entry(store: Any, world: World, text: str) -> int:
    """The entry the case is actually about — today's brain dump."""
    return store.create_entry(
        world.account_id, world.domain_id,
        occurred_on=time.strftime("%Y-%m-%d"), entry_mode="free",
        body=text, person_id=world.person_id,
    )
