"""The synthetic demonstration account.

Everything here is **invented**. No real person, no celebrity, no real assessment. The
account is flagged ``is_demo`` and synthetic content is never mixed with real records.

What it demonstrates, which is the whole reason it exists:

  * The same person produces **different outcomes under different profiles**, and that is
    not a contradiction. Sam fails under Husband KRYteria and passes under One Night Stand
    KRYteria; nothing in the app treats the first as the real verdict.
  * **Not Applicable** is a real answer, distinct from Unknown and from Fail.
  * A criterion carries **its own tier in each profile**.
  * A recurring theme with **counter-evidence stored beside it**.
  * One decision still open, one acted on.
  * A criterion that was **revised**, so My Progress has a changed priority to show.
  * Entries that are positive, negative, and genuinely ambiguous.

Run directly to build it:

    .venv/bin/python -m backend.seed_demo
"""

from __future__ import annotations

from datetime import date, timedelta

from .store import Store

DEMO_HANDLE = "demo"
DEMO_PASSPHRASE = "kryteria-demo-account"

#: Shown in the UI wherever demo content appears.
DEMO_NOTICE = (
    "This is a demonstration account. Every person, entry and assessment in it is "
    "invented. Nothing here describes a real person."
)


def _day(offset: int) -> str:
    return (date.today() - timedelta(days=offset)).isoformat()


def seed(store: Store, *, reset: bool = False) -> int:
    """Build the demo account. Returns its id."""
    existing = store.verify_account(DEMO_HANDLE, DEMO_PASSPHRASE)
    if existing is not None:
        if not reset:
            return existing
        store.delete_account(existing)

    account_id = store.create_account(DEMO_HANDLE, DEMO_PASSPHRASE, is_demo=True)
    dating = store.create_domain(account_id, "Dating", "romantic")

    # ---------------------------------------------------------------- library
    #
    # Deliberately mixed. "Soft hands" sits beside "Compatible relationship intentions"
    # because the product does not rank what matters to somebody.
    lib = {}
    for key, value, behaviour, why in [
        ("intentions", "Compatible relationship intentions",
         "Wants the same kind of relationship I do, and says so plainly",
         "I've spent too long guessing and calling it patience."),
        ("followthrough", "Follow-through",
         "Does what they said they would do",
         "When I let this slide I stop trusting my own read on things."),
        ("maturity", "Emotional maturity",
         "Can disagree without it becoming a fight or a silence", None),
        ("money", "Financial independence",
         "Covers their own obligations without it being a recurring drama", None),
        ("attraction", "Physical attraction", "I actually want to kiss him", None),
        ("chemistry", "Sexual chemistry", "It works, and we can talk about it", None),
        ("curiosity", "Intelligence and curiosity",
         "Asks real questions and is interested in the answers", None),
        ("kids", "Wants children",
         "Wants children, and within a timeframe that matches mine", None),
        ("independence", "Independent identity and interests",
         "Has a life of his own that he likes", None),
        ("discretion", "Discretion", "Keeps private things private", None),
        ("softhands", "Soft hands", "His hands are soft", None),
    ]:
        lib[key] = store.create_criterion(
            account_id, value=value, desired_behavior=behaviour, why_it_matters=why,
        )

    # A revision, so My Progress has a changed priority to show. The old version survives.
    store.revise_criterion(
        account_id, lib["followthrough"],
        revision_note="I was treating a changed plan the same as a broken promise. "
                      "They're not the same thing.",
        desired_behavior="Tells me in advance when something changes",
    )
    lib["followthrough"] = next(
        c["id"] for c in store.list_criteria(account_id)
        if c["value"] == "Follow-through"
    )

    # ---------------------------------------------------------------- profiles
    #
    # The same criterion, different tiers. Physical attraction is Preferred for a husband
    # and Mandatory for a one-night stand; wants-children is Mandatory in one profile and
    # Not Applicable in another. Both are legitimate and neither profile outranks the other.
    profiles = {}
    config = {
        "Husband KRYteria": ("Marriage", "Long-term", [
            ("intentions", "mandatory", "relevant"),
            ("followthrough", "mandatory", "relevant"),
            ("maturity", "mandatory", "relevant"),
            ("money", "mandatory", "relevant"),
            ("kids", "mandatory", "relevant"),
            ("curiosity", "mandatory", "relevant"),
            ("independence", "preferred", "relevant"),
            ("attraction", "preferred", "relevant"),
            ("chemistry", "mandatory", "relevant"),
            ("softhands", "aspirational", "relevant"),
        ]),
        "Boyfriend KRYteria": ("Exclusive dating", "Dating", [
            ("intentions", "mandatory", "relevant"),
            ("followthrough", "mandatory", "relevant"),
            ("maturity", "preferred", "relevant"),
            ("attraction", "mandatory", "relevant"),
            ("chemistry", "mandatory", "relevant"),
            ("curiosity", "preferred", "relevant"),
            ("money", "preferred", "relevant"),
            ("kids", "mandatory", "not_applicable"),
            ("softhands", "aspirational", "relevant"),
        ]),
        "Fuck Buddy KRYteria": ("Ongoing casual", "Ongoing casual", [
            ("attraction", "mandatory", "relevant"),
            ("chemistry", "mandatory", "relevant"),
            ("discretion", "mandatory", "relevant"),
            ("maturity", "preferred", "relevant"),
            ("followthrough", "preferred", "relevant"),
            ("kids", "mandatory", "not_applicable"),
            ("money", "preferred", "not_applicable"),
        ]),
        "One Night Stand KRYteria": ("One-time", "One-time", [
            ("attraction", "mandatory", "relevant"),
            ("chemistry", "mandatory", "relevant"),
            ("discretion", "preferred", "relevant"),
            ("kids", "mandatory", "not_applicable"),
            ("money", "mandatory", "not_applicable"),
            ("intentions", "mandatory", "not_applicable"),
        ]),
    }
    for name, (objective, label, rows) in config.items():
        pid = store.create_profile(account_id, name, objective=objective,
                                   context_label=label, domain_id=dating)
        profiles[name] = pid
        for key, tier, relevance in rows:
            store.add_criterion_to_profile(account_id, pid, lib[key], tier=tier, relevance=relevance)

    # ---------------------------------------------------------------- people
    sam = store.upsert_person(account_id, "Sam", domain_id=dating,
                              role_label="met in August")
    jordan = store.upsert_person(account_id, "Jordan", domain_id=dating,
                                 role_label="three months")

    # ---------------------------------------------------------------- entries
    #
    # Positive, negative and genuinely ambiguous. The recurring theme is Sam's
    # short-notice changes; the counter-evidence is that he does show up when it matters.
    # Themes are what each entry was ABOUT, from the closed vocabulary in
    # data/themes.json. Seeded here so the demo shows the thing themes exist for: the
    # user keeps writing about reciprocity and expectations with Sam, and about
    # emotional intimacy with Jordan — a pattern across entries that no single entry
    # contains, and that she never created a criterion for.
    entries = {}
    themes_by_key: dict[str, list[str]] = {
        "sam1": ["attraction-and-chemistry"],
        "sam2": ["reciprocity-and-initiative", "communication-preferences"],
        "sam3": ["expectations-and-commitment", "expressing-needs"],
        "sam4": ["reciprocity-and-initiative", "communication-preferences"],
        "sam5": ["reciprocity-and-initiative", "feeling-valued"],
        "jordan1": ["emotional-intimacy", "feeling-valued"],
        "jordan2": ["emotional-intimacy", "expressing-needs"],
        "jordan3": ["expectations-and-commitment", "emotional-intimacy"],
    }
    for key, person, days_ago, text in [
        ("sam1", sam, 34,
         "Drinks with Sam. He is genuinely one of the most attractive people I have ever "
         "been in a room with and I could not tell you one thing he said."),
        ("sam2", sam, 27,
         "Sam moved our plans to Sunday on Saturday night. Again. He was lovely about it "
         "and he did show up on Sunday."),
        ("sam3", sam, 20,
         "Asked Sam straight out what he's looking for. He said he doesn't really think "
         "about it like that. I don't know what to do with that answer."),
        ("sam4", sam, 13,
         "Sam cancelled an hour before. Said work. He's between jobs so I'm not sure what "
         "work that is, but I didn't ask."),
        ("sam5", sam, 6,
         "My car wouldn't start at 11pm and Sam drove across town without being asked. "
         "So he does show up. Just not for dinner."),
        ("jordan1", jordan, 40,
         "Jordan asked about my work for an hour and actually listened. Paid for dinner "
         "without making it a thing. His hands were SO soft lol."),
        ("jordan2", jordan, 25,
         "Jordan got upset when I disagreed with him about something. He didn't raise his "
         "voice — said he needed a few minutes, came back and apologised."),
        ("jordan3", jordan, 11,
         "Jordan said he wants kids in the next few years and asked what I wanted. First "
         "time anyone has just asked."),
    ]:
        entries[key] = store.create_entry(
            account_id, dating, occurred_on=_day(days_ago), entry_mode="free",
            body=text, people=[("Sam" if person == sam else "Jordan")],
            person_id=person,
        )
        store.save_themes(account_id, entries[key], themes_by_key.get(key, []))

    # ---------------------------------------------------------------- observations
    #
    # Marked as the demo's own, with the fact/interpretation split intact.
    store.save_observations(account_id, entries["sam2"], [
        {"kind": "reported_event",
         "text": "Sam moved the plans the night before.", "certainty": "stated"},
        {"kind": "reported_event",
         "text": "Sam attended the rescheduled plans.", "certainty": "stated"},
        {"kind": "emotional_reaction",
         "text": "She noted it as a repeat.", "certainty": "stated"},
    ])
    store.save_observations(account_id, entries["sam4"], [
        {"kind": "reported_event", "text": "Sam cancelled an hour beforehand.",
         "certainty": "stated"},
        {"kind": "missing_information",
         "text": "What the work commitment was.", "certainty": "stated"},
        {"kind": "uncertainty",
         "text": "She chose not to ask.", "certainty": "inferred",
         "hedge": "It reads as though you decided not to push on it. Is that right?"},
    ])
    store.save_observations(account_id, entries["sam5"], [
        {"kind": "reported_event",
         "text": "Sam drove across town late at night, unprompted, to help.",
         "certainty": "stated"},
    ])
    store.save_observations(account_id, entries["jordan2"], [
        {"kind": "reported_event", "text": "Jordan became upset during a disagreement.",
         "certainty": "stated"},
        {"kind": "reported_event",
         "text": "Jordan asked for a few minutes, returned, and apologised.",
         "certainty": "stated"},
    ])

    # ---------------------------------------------------------------- a pattern
    #
    # Three supporting entries and two that cut against it, stored side by side. The
    # finding is moderate, so it must offer an alternative explanation — and it does.
    store.save_pattern(
        account_id, profile_id=profiles["Boyfriend KRYteria"], domain_id=dating,
        kind="recurring_unmet_need",
        statement="Plans with Sam have changed at short notice on three occasions.",
        criterion_id=lib["followthrough"],
        evidence_strength="moderate",
        alternatives=[
            "Three changes over five weeks may be a period rather than a habit.",
            "He has not been asked whether something recurring is causing them.",
        ],
        uncertainties=["How far in advance each plan was originally made."],
        evidence=[
            {"entry_id": entries["sam2"]},
            {"entry_id": entries["sam4"]},
            {"entry_id": entries["sam1"]},
            {"entry_id": entries["sam5"], "stance": "contradicts"},
            {"entry_id": entries["sam3"], "stance": "contradicts"},
        ],
    )

    # ---------------------------------------------------------------- assessments
    #
    # THE DEMONSTRATION. Sam fails the long-term profiles and passes the casual ones.
    # Jordan passes across the board. Neither outcome is a verdict about either person,
    # and the casual profiles are not a consolation prize.
    def assess(profile: str, key: str, person: int, status: str, note: str | None = None):
        store.set_assessment(account_id, profiles[profile], lib[key], person, status,
                             note=note, origin="user")

    for profile in ("Husband KRYteria", "Boyfriend KRYteria"):
        assess(profile, "intentions", sam, "fail",
               "Asked directly; he doesn't think about it that way.")
        assess(profile, "followthrough", sam, "fail")
        assess(profile, "attraction", sam, "pass")
        assess(profile, "chemistry", sam, "pass")
        assess(profile, "maturity", sam, "unknown")
    assess("Husband KRYteria", "money", sam, "unknown",
           "Between jobs. One cancellation doesn't settle this either way.")
    assess("Husband KRYteria", "kids", sam, "unknown")

    for profile in ("Fuck Buddy KRYteria", "One Night Stand KRYteria"):
        assess(profile, "attraction", sam, "pass")
        assess(profile, "chemistry", sam, "pass")
        assess(profile, "discretion", sam, "pass")
    assess("Fuck Buddy KRYteria", "maturity", sam, "unknown")
    assess("Fuck Buddy KRYteria", "followthrough", sam, "unknown",
           "Matters much less here than it does for dinner plans.")

    for profile in ("Husband KRYteria", "Boyfriend KRYteria"):
        assess(profile, "intentions", jordan, "pass", "He asked, directly.")
        assess(profile, "curiosity", jordan, "pass")
        assess(profile, "attraction", jordan, "pass")
        assess(profile, "chemistry", jordan, "pass")
        assess(profile, "followthrough", jordan, "pass")
        assess(profile, "maturity", jordan, "unknown",
               "One difficult conversation handled well is not yet a pattern.")
        assess(profile, "softhands", jordan, "pass")
    assess("Husband KRYteria", "kids", jordan, "pass")
    assess("Husband KRYteria", "money", jordan, "unknown")

    for profile in ("Fuck Buddy KRYteria", "One Night Stand KRYteria"):
        assess(profile, "attraction", jordan, "pass")
        assess(profile, "chemistry", jordan, "pass")
        assess(profile, "discretion", jordan, "pass")

    # Jordan reads Pass as a boyfriend and Unknown as a husband, and that is the more
    # interesting half of the demonstration: the difference is not "casual versus
    # serious", it is which questions each objective actually asks. Two of his Husband
    # criteria have no evidence yet, so the honest answer is that we do not know —
    # displayed exactly as prominently as a Pass would be.

    # ---------------------------------------------------------------- decisions
    #
    # One acted on, one still open, and a run of postponements so the signature question
    # has something real behind it.
    store.record_decision(
        account_id, choice="talk", criterion_id=lib["intentions"],
        action_text="Ask Sam directly what he's looking for.",
    )
    for _ in range(3):
        store.record_decision(account_id, choice="more_time",
                              criterion_id=lib["followthrough"],
                              action_text="See whether the next two plans hold.")
    store.record_decision(account_id, choice="undecided", criterion_id=lib["maturity"])

    # ---------------------------------------------------------------- resources
    # Every resources_*.json, not just the US one — so adding a country's file is the
    # only step needed, and nobody has to remember to wire it up here.
    if not store.list_resources(region="US"):
        import json
        from pathlib import Path

        data = Path(__file__).resolve().parent.parent / "data"
        for path in sorted(data.glob("resources_*.json")):
            rows = json.loads(path.read_text(encoding="utf-8")).get("resources", [])
            if rows:
                store.seed_resources(rows)

    return account_id


def main() -> None:  # pragma: no cover
    store = Store()
    account_id = seed(store, reset=True)
    print(f"Demo account ready (id {account_id}).")
    print(f"  handle:     {DEMO_HANDLE}")
    print(f"  passphrase: {DEMO_PASSPHRASE}")
    print()
    print(DEMO_NOTICE)


if __name__ == "__main__":  # pragma: no cover
    main()
