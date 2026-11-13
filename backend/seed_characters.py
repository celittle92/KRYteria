"""Build the nine-character demo ecosystem from ``data/characters/*.json``.

Why the character data is JSON and not Python
---------------------------------------------
``seed_demo.py`` builds one account in 360 lines of hand-written Python. Nine richer
accounts in that style would be two thousand lines that only a programmer could check,
and the thing most needing checking here is the *narrative* — whether Jane's criteria
match who Jane is, whether an entry supports the assessment it is supposed to support.
That review belongs to whoever wrote the characters, so the characters live in a file
that can be read and corrected without reading code.

It also means the specification and the fixture cannot drift: the JSON *is* the spec,
loaded directly.

Each character is one account. The people they date are alias rows inside their own
account and nothing more — "Adrian" in Catherine's account and the account belonging to
Adrian are unrelated rows that share a string. That separation is the product's central
privacy promise, and this module is the only place in the codebase with the power to
break it, because it is the only thing holding every account open at once. See
``assert_no_cross_account_links`` at the bottom, and the test that calls it.

Run it:

    .venv/bin/python -m backend.seed_characters            # build them
    .venv/bin/python -m backend.seed_characters --reset    # rebuild from scratch
    .venv/bin/python -m backend.seed_characters --check    # validate the JSON only
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .store import (
    CONCERN_LEVELS,
    DECISION_CHOICES,
    EVIDENCE_STRENGTHS,
    GAP_KINDS,
    SAFETY_CATEGORIES,
    SOURCE_LEVELS,
    Store,
    StoreError,
)

HERE = Path(__file__).resolve().parent
CHARACTERS_DIR = HERE.parent / "data" / "characters"

#: Every demo account's passphrase is this prefix plus its handle. These are published
#: in README.md on purpose: the accounts hold nothing but invented content, and a demo
#: nobody can sign into is not a demo. Never follow this pattern for a real account.
PASSPHRASE_PREFIX = "kryteria-demo-"

DEMO_NOTICE = (
    "Demonstration account. Every person, entry, observation and assessment in it is "
    "invented. Nothing here describes a real person."
)

TIERS = ("mandatory", "preferred", "aspirational")
RELEVANCE = ("relevant", "not_applicable")
STATUSES = ("pass", "unknown", "fail", "not_applicable")
RELATIONS = ("supporting", "contradicting", "complicating", "unrelated")
KINDS = ("reported_event", "interpretation", "emotional_reaction",
         "missing_information", "uncertainty")


def _day(offset: int) -> str:
    return (date.today() - timedelta(days=offset)).isoformat()


def passphrase_for(handle: str) -> str:
    return f"{PASSPHRASE_PREFIX}{handle}"


# ───────────────────────────────── loading ─────────────────────────────────

def load_character_files() -> list[dict[str, Any]]:
    """Read every character file, sorted so the build order is stable."""
    if not CHARACTERS_DIR.is_dir():
        raise StoreError(f"No character directory at {CHARACTERS_DIR}")
    out = []
    for path in sorted(CHARACTERS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise StoreError(f"{path.name} is not valid JSON: {e}") from e
        data["_source"] = path.name
        out.append(data)
    if not out:
        raise StoreError(f"No character files in {CHARACTERS_DIR}")
    return out


def validate(char: dict[str, Any], themes: set[str]) -> list[str]:
    """Every problem in one character file, as a list rather than the first one.

    A seeder that fails on the first bad key makes you re-run it once per typo. This
    reports everything wrong with a file in one pass, naming the character and the key.
    """
    where = char.get("_source", char.get("handle", "?"))
    problems: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            problems.append(f"{where}: {msg}")

    for field in ("handle", "display_name", "criteria", "profiles"):
        need(bool(char.get(field)), f"missing required field {field!r}")
    if problems:
        return problems

    crit_keys = {c["key"] for c in char["criteria"]}
    person_keys = {p["key"] for p in char.get("people", [])}
    entry_keys = {e["key"] for e in char.get("entries", [])}
    profile_names = {p["name"] for p in char["profiles"]}

    need(len(crit_keys) == len(char["criteria"]), "duplicate criterion key")
    need(len(person_keys) == len(char.get("people", [])), "duplicate person key")
    need(len(entry_keys) == len(char.get("entries", [])), "duplicate entry key")

    for p in char["profiles"]:
        for row in p.get("criteria", []):
            need(row["key"] in crit_keys,
                 f"profile {p['name']!r} uses unknown criterion {row['key']!r}")
            need(row.get("tier", "preferred") in TIERS,
                 f"profile {p['name']!r}: bad tier {row.get('tier')!r}")
            need(row.get("relevance", "relevant") in RELEVANCE,
                 f"profile {p['name']!r}: bad relevance {row.get('relevance')!r}")

    for e in char.get("entries", []):
        need(e.get("person") in person_keys or e.get("person") is None,
             f"entry {e['key']!r} names unknown person {e.get('person')!r}")
        for t in e.get("themes", []):
            need(t in themes, f"entry {e['key']!r} uses unknown theme {t!r}")
        for o in e.get("observations", []):
            need(o["kind"] in KINDS, f"entry {e['key']!r}: bad kind {o['kind']!r}")
            need(o.get("certainty", "stated") != "inferred" or o.get("hedge"),
                 f"entry {e['key']!r}: an inferred observation needs a hedge")
        for ev in e.get("evidence", []):
            need(ev["criterion"] in crit_keys,
                 f"entry {e['key']!r}: evidence names unknown criterion {ev['criterion']!r}")
            need(ev["relation"] in RELATIONS,
                 f"entry {e['key']!r}: bad relation {ev['relation']!r}")

    for a in char.get("assessments", []):
        need(a["profile"] in profile_names,
             f"assessment names unknown profile {a['profile']!r}")
        need(a["criterion"] in crit_keys,
             f"assessment names unknown criterion {a['criterion']!r}")
        need(a["person"] in person_keys,
             f"assessment names unknown person {a['person']!r}")
        need(a["status"] in STATUSES, f"assessment has bad status {a['status']!r}")

    for pat in char.get("patterns", []):
        for ekey in [x["entry"] for x in pat.get("evidence", [])]:
            need(ekey in entry_keys, f"pattern cites unknown entry {ekey!r}")
        if pat.get("criterion"):
            need(pat["criterion"] in crit_keys,
                 f"pattern names unknown criterion {pat['criterion']!r}")
        need(pat.get("evidence_strength", "insufficient") in EVIDENCE_STRENGTHS,
             f"pattern has bad evidence_strength {pat.get('evidence_strength')!r}")

    for s in char.get("safety_events", []):
        need(s.get("entry") in entry_keys,
             f"safety event names unknown entry {s.get('entry')!r}")
        need(s.get("category") in SAFETY_CATEGORIES,
             f"safety event has bad category {s.get('category')!r}")
        need(s.get("concern_level", "potential") in CONCERN_LEVELS,
             f"safety event has bad concern_level {s.get('concern_level')!r}")

    # These three were added after a bad `gap_kind` got past validation and failed
    # halfway through building an account. Every closed vocabulary the store enforces
    # is checked here too, so a typo fails at --check rather than against the database.
    for q in char.get("interrogations", []):
        need(q.get("entry") in entry_keys,
             f"interrogation names unknown entry {q.get('entry')!r}")
        need(q.get("gap_kind") in GAP_KINDS,
             f"interrogation has bad gap_kind {q.get('gap_kind')!r} "
             f"(one of {', '.join(GAP_KINDS)})")
        need(q.get("claim_valence", "negative") in ("negative", "positive", "neutral"),
             f"interrogation has bad claim_valence {q.get('claim_valence')!r}")

    for d in char.get("decisions", []):
        need(d.get("choice") in DECISION_CHOICES,
             f"decision has bad choice {d.get('choice')!r}")
        if d.get("criterion"):
            need(d["criterion"] in crit_keys,
                 f"decision names unknown criterion {d['criterion']!r}")

    for e in char.get("entries", []):
        for ev in e.get("evidence", []):
            need(ev.get("source_level", "agent_hypothesis") in SOURCE_LEVELS,
                 f"entry {e['key']!r}: bad source_level {ev.get('source_level')!r}")
            need(not ev.get("profile") or ev["profile"] in profile_names,
                 f"entry {e['key']!r}: evidence names unknown profile {ev.get('profile')!r}")

    return problems


# ───────────────────────────────── building ─────────────────────────────────

def build_character(store: Store, char: dict[str, Any]) -> int:
    """Create one account and everything in it. Returns the account id."""
    handle = char["handle"]
    account_id = store.create_account(handle, passphrase_for(handle), is_demo=True)
    domain_id = store.create_domain(account_id, "Dating", "romantic")

    # ---- criteria library (no tier here; a tier belongs to a profile, not a criterion)
    lib: dict[str, int] = {}
    for c in char["criteria"]:
        lib[c["key"]] = store.create_criterion(
            account_id, value=c["value"],
            desired_behavior=c.get("desired_behavior"),
            why_it_matters=c.get("why_it_matters"),
        )

    # ---- revisions, so a changed standard is visible as history rather than a rewrite
    for rev in char.get("criterion_revisions", []):
        store.revise_criterion(
            account_id, lib[rev["key"]],
            revision_note=rev["note"],
            desired_behavior=rev.get("desired_behavior"),
        )
        value = next(c["value"] for c in char["criteria"] if c["key"] == rev["key"])
        lib[rev["key"]] = next(
            c["id"] for c in store.list_criteria(account_id) if c["value"] == value
        )

    # ---- profiles
    profiles: dict[str, int] = {}
    for p in char["profiles"]:
        pid = store.create_profile(
            account_id, p["name"], objective=p.get("objective"),
            context_label=p.get("context_label"), domain_id=domain_id,
        )
        profiles[p["name"]] = pid
        for row in p.get("criteria", []):
            store.add_criterion_to_profile(
                account_id, pid, lib[row["key"]],
                tier=row.get("tier", "preferred"),
                relevance=row.get("relevance", "relevant"),
            )

    # ---- people: aliases inside THIS account, related to nothing outside it
    people: dict[str, int] = {}
    for person in char.get("people", []):
        people[person["key"]] = store.upsert_person(
            account_id, person["alias"], domain_id=domain_id,
            role_label=person.get("role_label"),
        )

    # ---- entries, themes, observations, evidence
    entries: dict[str, int] = {}
    for e in char.get("entries", []):
        pid = people.get(e.get("person"))
        alias = next((p["alias"] for p in char.get("people", [])
                      if p["key"] == e.get("person")), None)
        entry_id = store.create_entry(
            account_id, domain_id, occurred_on=_day(e["days_ago"]),
            entry_mode=e.get("entry_mode", "free"), body=e["body"],
            people=[alias] if alias else [], person_id=pid,
        )
        entries[e["key"]] = entry_id
        if e.get("themes"):
            store.save_themes(account_id, entry_id, e["themes"])
        if e.get("observations"):
            store.save_observations(account_id, entry_id, [
                {"kind": o["kind"], "text": o["text"],
                 "certainty": o.get("certainty", "stated"),
                 **({"hedge": o["hedge"]} if o.get("hedge") else {})}
                for o in e["observations"]
            ])
        for ev in e.get("evidence", []):
            store.link_evidence(
                account_id, entry_id=entry_id, criterion_id=lib[ev["criterion"]],
                relation=ev["relation"],
                profile_id=profiles.get(ev["profile"]) if ev.get("profile") else None,
                person_id=pid, rationale=ev.get("rationale"),
                source_level=ev.get("source_level", "agent_hypothesis"),
                proposed_by="agent",
            )

    # ---- patterns
    for pat in char.get("patterns", []):
        store.save_pattern(
            account_id,
            profile_id=profiles.get(pat.get("profile")) if pat.get("profile") else None,
            domain_id=domain_id, kind=pat["kind"], statement=pat["statement"],
            criterion_id=lib[pat["criterion"]] if pat.get("criterion") else None,
            evidence_strength=pat.get("evidence_strength", "insufficient"),
            alternatives=pat.get("alternatives", []),
            uncertainties=pat.get("uncertainties", []),
            evidence=[{"entry_id": entries[x["entry"]],
                       **({"stance": x["stance"]} if x.get("stance") else {})}
                      for x in pat.get("evidence", [])],
        )

    # ---- assessments. origin "user": nothing here was decided by an agent.
    for a in char.get("assessments", []):
        store.set_assessment(
            account_id, profiles[a["profile"]], lib[a["criterion"]],
            people[a["person"]], a["status"], note=a.get("note"), origin="user",
        )

    # ---- interrogations: a question about a claim, never about the person asking
    for q in char.get("interrogations", []):
        store.save_interrogation(
            account_id, entry_id=entries[q["entry"]], claim=q["claim"],
            gap_kind=q["gap_kind"], question=q["question"],
            claim_valence=q.get("claim_valence", "negative"),
            materiality=q.get("materiality", "material"),
        )

    # ---- decisions
    for d in char.get("decisions", []):
        for _ in range(d.get("times", 1)):
            store.record_decision(
                account_id, choice=d["choice"],
                criterion_id=lib[d["criterion"]] if d.get("criterion") else None,
                action_text=d.get("action_text"),
            )

    # ---- safety events. No profile_id: the safety layer does not take one.
    for s in char.get("safety_events", []):
        store.log_safety_event(
            account_id=account_id, entry_id=entries[s["entry"]],
            trigger=s["trigger"], action=s["action"],
            category=s.get("category"), concern_level=s.get("concern_level", "potential"),
            detail=s.get("detail"),
        )

    return account_id


# ──────────────────────────── the privacy assertion ────────────────────────────

def assert_no_cross_account_links(store: Store) -> None:
    """No row in one account may reference a row in another. Checked, not trusted.

    Every API path is already guarded twice — ``_assert_owns`` in the store and the
    route's own account scoping. This seeder bypasses both, because it legitimately
    holds all nine accounts open at once. It is therefore the one component that could
    create the link nothing else can, and a link created here would be invisible: the
    data would simply be wrong in a way that only shows up as one user seeing another's
    record.

    So it is asserted directly against the database after the build.
    """
    checks = [
        ("entries", "person_id", "people"),
        ("entries", "domain_id", "domains"),
        ("profiles", "domain_id", "domains"),
        ("profile_criteria", "criterion_id", "criteria"),
        ("assessments", "criterion_id", "criteria"),
        ("assessments", "person_id", "people"),
        ("assessments", "profile_id", "profiles"),
        ("evidence_links", "entry_id", "entries"),
        ("evidence_links", "criterion_id", "criteria"),
        ("observations", "entry_id", "entries"),
        ("entry_themes", "entry_id", "entries"),
        ("safety_events", "entry_id", "entries"),
    ]
    conn = store._connect()
    broken: list[str] = []
    checked = 0
    for table, column, parent in checks:
        sql = (
            f"SELECT COUNT(*) FROM {table} t "
            f"JOIN {parent} p ON p.id = t.{column} "
            f"WHERE t.account_id IS NOT NULL AND p.account_id IS NOT NULL "
            f"AND t.account_id != p.account_id"
        )
        try:
            n = conn.execute(sql).fetchone()[0]
        except Exception:
            continue          # table or column absent in this schema; nothing to check
        checked += 1
        if n:
            broken.append(f"{table}.{column} -> {parent}: {n} row(s) cross accounts")
    if checked == 0:
        # A check that silently examines nothing is worse than no check, because it
        # reads as a passing assertion in the test output.
        raise StoreError(
            "assert_no_cross_account_links examined no tables — the schema moved "
            "underneath it and it is no longer checking anything."
        )
    if broken:
        raise StoreError(
            "The seeder created a cross-account reference, which the product promises "
            "cannot exist:\n  " + "\n  ".join(broken)
        )


# ───────────────────────────────── entry point ─────────────────────────────────

def seed(store: Store, *, reset: bool = False) -> dict[str, int]:
    """Build every character. Returns handle -> account id."""
    themes = {t["id"] for t in json.loads(
        (HERE.parent / "data" / "themes.json").read_text(encoding="utf-8"))["themes"]}

    chars = load_character_files()
    problems: list[str] = []
    for c in chars:
        problems.extend(validate(c, themes))
    if problems:
        raise StoreError("Character files are invalid:\n  " + "\n  ".join(problems))

    built: dict[str, int] = {}
    for c in chars:
        existing = store.verify_account(c["handle"], passphrase_for(c["handle"]))
        if existing is not None:
            if not reset:
                built[c["handle"]] = existing
                continue
            store.delete_account(existing)
        built[c["handle"]] = build_character(store, c)

    assert_no_cross_account_links(store)
    return built


def main() -> int:  # pragma: no cover - convenience entry point
    import sys

    check_only = "--check" in sys.argv
    themes = {t["id"] for t in json.loads(
        (HERE.parent / "data" / "themes.json").read_text(encoding="utf-8"))["themes"]}
    chars = load_character_files()

    problems: list[str] = []
    for c in chars:
        problems.extend(validate(c, themes))
    if problems:
        print("INVALID:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"{len(chars)} character file(s) valid: "
          f"{', '.join(c['display_name'] for c in chars)}")
    if check_only:
        return 0

    store = Store()
    built = seed(store, reset="--reset" in sys.argv)
    print(f"\nSeeded {len(built)} demo accounts. All content is synthetic.\n")
    for c in chars:
        print(f"  {c['display_name']:10} handle {c['handle']:20} "
              f"passphrase {passphrase_for(c['handle'])}")
    print(f"\n{DEMO_NOTICE}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
