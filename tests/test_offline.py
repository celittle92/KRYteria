#!/usr/bin/env python3
"""Offline tests for KRYteria's store layer. Free — no model call, no network.

These cover the rules that are the product rather than the plumbing: criteria versioning,
the refusal to write an unsupported pattern, the fact/interpretation firewall, and
postponement counting. Run them to verify an edit; never a live agent run.

    python3 tests/test_offline.py

``pwdlib`` is stubbed so these run before the venv exists. The real hashing is exercised
by tests/test_security.py once dependencies are installed.
"""

from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

# --- stub backend.security so these tests need no third-party packages ---------------
_fake = types.ModuleType("backend.security")
_fake.hash_passphrase = lambda p: f"stub${p}"          # type: ignore[attr-defined]
_fake.verify_passphrase = lambda p, h: h == f"stub${p}"  # type: ignore[attr-defined]
sys.modules["backend.security"] = _fake

from backend.store import MIN_SUPPORT, POSTPONEMENT_PROBE_AT, Store, StoreError  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{label}{(' — ' + detail) if detail else ''}")


def expect_raises(label: str, exc: type[Exception], fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
    except exc:
        check(label, True)
    except Exception as e:  # pragma: no cover - diagnostic path
        check(label, False, f"raised {type(e).__name__}: {e}")
    else:
        check(label, False, "no exception raised")


def fresh() -> tuple[Store, int, int]:
    db = Path(tempfile.mkdtemp()) / "t.db"
    s = Store(db)
    acct = s.create_account("tester", "a-long-enough-passphrase")
    dom = s.create_domain(acct, "Dating", "romantic")
    return s, acct, dom


def fresh_profile(name: str = "Boyfriend KRYteria") -> tuple[Store, int, int, int]:
    s, acct, dom = fresh()
    prof = s.create_profile(acct, name, objective="Exclusive dating", domain_id=dom)
    return s, acct, dom, prof


# ---------------------------------------------------------------- themes

def test_theme_vocabulary_is_closed() -> None:
    """A model free to invent labels makes 'this keeps coming up' meaningless."""
    from backend.themes import UnknownTheme, ids, validate

    check("the vocabulary loads", len(ids()) == 10, str(len(ids())))
    check("ids are kebab-case slugs, not prose",
          all(i == i.lower() and " " not in i for i in ids()))
    expect_raises("an invented theme is refused", UnknownTheme,
            validate, ["emotional-intimacy", "vibes"])
    check("duplicates collapse",
          validate(["emotional-intimacy", "emotional-intimacy"]) == ["emotional-intimacy"])
    check("order follows the vocabulary, not the caller",
          validate(["boundaries-and-consent", "attraction-and-chemistry"])
          == ["attraction-and-chemistry", "boundaries-and-consent"])


def test_themes_are_stored_against_entries_and_counted() -> None:
    s, acct, dom = fresh()
    person = s.upsert_person(acct, "A")
    other = s.upsert_person(acct, "B")
    for body, themes, pid in [
        ("He never texts first.", ["reciprocity-and-initiative",
                                   "communication-preferences"], person),
        ("I didn't want to bring it up again.", ["expressing-needs"], person),
        ("Same thing, I'm always the one reaching out.",
         ["reciprocity-and-initiative"], person),
        ("Completely different person, lovely evening.",
         ["affection-and-comfort"], other),
    ]:
        e = s.create_entry(acct, dom, body=body, person_id=pid)
        s.save_themes(acct, e, themes)

    trends = {r["theme_id"]: r for r in s.theme_trends(acct)}
    check("the recurring theme leads", list(trends)[0] == "reciprocity-and-initiative")
    check("it is counted across entries", trends["reciprocity-and-initiative"]["entries"] == 2)
    check("a one-off is counted once", trends["expressing-needs"]["entries"] == 1)
    check("first and last seen are recorded",
          bool(trends["expressing-needs"]["first_seen"]
               and trends["expressing-needs"]["last_seen"]))

    per_person = {r["theme_id"] for r in s.theme_trends(acct, person_id=person)}
    check("per-person trends exclude another person's entries",
          "affection-and-comfort" not in per_person)
    check("and keep that person's own", "reciprocity-and-initiative" in per_person)


def test_a_theme_is_not_an_assessment() -> None:
    """Structural, not a style note: there is nowhere to put a verdict.

    A theme says a subject came up. The moment it carries a status it becomes a
    judgement about a person that the user never confirmed.
    """
    s, _, _ = fresh()
    with s.read() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(entry_themes)")}
    for forbidden in ("status", "score", "rating", "relation", "evidence_strength"):
        check(f"entry_themes has no {forbidden} column", forbidden not in cols)


def test_themes_are_validated_at_the_store_not_trusted() -> None:
    from backend.themes import UnknownTheme

    s, acct, dom = fresh()
    e = s.create_entry(acct, dom, body="x")
    expect_raises("the store refuses an unknown theme", UnknownTheme,
            s.save_themes, acct, e, ["not-a-real-theme"])
    check("nothing was written", s.list_entry_themes(acct, e) == [])


def test_discarding_an_entry_removes_its_themes() -> None:
    """'He wrote about sexual consideration on the 3rd' is exactly what discard means.

    Themes survive analysis_only, like observations — that mode keeps the analysis by
    definition. They must not survive discard.
    """
    s, acct, dom = fresh()
    kept = s.create_entry(acct, dom, body="Lovely evening.")
    s.save_themes(acct, kept, ["affection-and-comfort"])
    s.apply_retention(acct, kept, "analysis_only")
    check("analysis_only keeps the themes",
          s.list_entry_themes(acct, kept) == ["affection-and-comfort"])

    gone = s.create_entry(acct, dom, body="Something I'd rather not keep.")
    s.save_themes(acct, gone, ["sexual-consideration", "boundaries-and-consent"])
    s.apply_retention(acct, gone, "discard")
    check("discard removes them", s.list_entry_themes(acct, gone) == [])


def test_another_account_cannot_reach_or_count_themes() -> None:
    from backend.store import NotOwned

    s, acct, dom = fresh()
    e = s.create_entry(acct, dom, body="x")
    s.save_themes(acct, e, ["emotional-intimacy"])
    intruder = s.create_account("intruder", "a-long-enough-passphrase")
    expect_raises("listing another account's entry themes is refused", NotOwned,
            s.list_entry_themes, intruder, e)
    expect_raises("saving against another account's entry is refused", NotOwned,
            s.save_themes, intruder, e, ["emotional-intimacy"])
    check("and the intruder's own trends are empty", s.theme_trends(intruder) == [])


def test_another_account_cannot_plant_or_see_a_checklist_observation() -> None:
    """The one hole an audit found, and the shape of it is worth remembering.

    ``record_checklist_observation`` took ``account_id`` and only *stamped* it on the
    row — it never checked it — and ``list_checklist``'s count query grouped by item and
    person with no account at all. So a write from one session could be counted onto
    another account's screen. Stamping an id is not the same as asserting it, and this
    test exists because those two read almost identically at a glance.
    """
    from backend.store import NotOwned

    s, acct, dom = fresh()
    crit = s.create_criterion(acct, value="Soft hands", desired_behavior="soft")
    prof = s.create_profile(acct, "P")
    s.add_criterion_to_profile(acct, prof, crit)
    person = s.upsert_person(acct, "A")
    item = s.save_checklist_items(
        acct, crit, [{"text": "x", "source_level": "agent_hypothesis"}])[0]
    s.record_checklist_observation(acct, item, person_id=person, state="observed")
    check("the owner's own observation counts",
          s.list_checklist(acct, crit, person_id=person)[0]["times_observed"] == 1)

    intruder = s.create_account("intruder", "a-long-enough-passphrase")
    expect_raises("another account cannot observe against this item", NotOwned,
            s.record_checklist_observation, intruder, item, person_id=person)
    check("and the owner's counts are untouched",
          s.list_checklist(acct, crit, person_id=person)[0]["times_observed"] == 1)


def test_the_prompt_block_is_built_from_the_vocabulary() -> None:
    """So the file the store validates against and the list the model sees cannot drift."""
    from backend.themes import ids, prompt_block

    block = prompt_block()
    for tid in ids():
        check(f"{tid} reaches the prompt", f"`{tid}`" in block)
    check("the consent theme carries its warning into the prompt",
          "NOT A SAFETY RESPONSE" in block.upper())


def test_resources_match_where_the_user_says_they_are() -> None:
    """A US number offered to somebody in Osaka is not a smaller failure than an
    invented one — it is the same failure with a real number attached.

    Christine, 2026-11-12: the agent should be able to pull safety numbers for countries
    outside the US and Canada.
    """
    s, acct, _ = fresh()
    _seed_resources(s)
    s.seed_resources([
        {"name": "A nationwide line in Japan", "kind": "confidential_support",
         "region": "JP", "categories": [], "phone": "(verified example)",
         "verified_at": "2026-11-12"},
        {"name": "A service that really is worldwide", "kind": "information",
         "region": "GLOBAL", "categories": [], "url": "https://example.edu/global",
         "verified_at": "2026-11-12"},
    ])

    us = {r["name"] for r in s.list_resources(region="US")}
    jp = {r["name"] for r in s.list_resources(region="JP")}
    check("a US account does not see the Japanese line",
          "A nationwide line in Japan" not in us)
    check("a Japanese account does not see US hotlines",
          not any("National Domestic Violence" in n for n in jp), str(jp))
    check("but does see its own", "A nationwide line in Japan" in jp)
    check("global services reach both",
          "A service that really is worldwide" in us & jp)

    # The default is no longer "US" — that was the bug.
    unset = {r["name"] for r in s.list_resources()}
    check("an account that has not said its country gets global only",
          unset == {"A service that really is worldwide"}, str(unset))
    check("and a country with nothing curated gets an honest empty list",
          s.list_resources(region="KE", include_global=False) == [])

    # A country-specific row outranks a global one.
    ordered = [r["name"] for r in s.list_resources(region="JP", kind="confidential_support")]
    check("local services are listed before global ones",
          ordered[0] == "A nationwide line in Japan" if ordered else False, str(ordered))


def test_region_is_set_by_the_user_and_can_be_withdrawn() -> None:
    s, acct, _ = fresh()
    check("it starts unset", (s.get_account(acct) or {}).get("region") is None)

    s.set_preferences(acct, region="jp")
    check("it is stored uppercase", s.get_account(acct)["region"] == "JP")

    s.set_preferences(acct, region="")
    check("an empty string clears it — a location given can be taken back",
          s.get_account(acct)["region"] is None)

    s.set_preferences(acct, region="GB")
    s.set_preferences(acct, theme="warm")
    check("an unrelated preference change leaves it alone",
          s.get_account(acct)["region"] == "GB")

    expect_raises("free text is refused", StoreError,
                  s.set_preferences, acct, region="somewhere in east africa")
    expect_raises("a three-letter code is refused", StoreError,
                  s.set_preferences, acct, region="JPN")


def test_a_resource_must_declare_its_country() -> None:
    """It used to default to 'US', filing every foreign service under the wrong flag."""
    s, _, _ = fresh()
    expect_raises("a resource with no region is refused", StoreError,
                  s.seed_resources, [{"name": "Nowhere", "kind": "information",
                                      "url": "https://example.edu/x",
                                      "verified_at": "2026-11-12"}])
    expect_raises("still refused without a verification date", StoreError,
                  s.seed_resources, [{"name": "Unchecked", "kind": "information",
                                      "region": "GB", "url": "https://example.edu/x"}])


def test_every_resource_is_dated_and_sourced() -> None:
    """A number you can see was checked — and when — is one you can judge.

    Verifying six countries on 2026-11-12 found two dead government pages, one
    organisation's site down, and one organisation contradicting itself about its own
    phone number. Against that, a bare undated number asks for a trust nobody can earn.
    """
    import datetime as _dt

    blob = json.loads(
        (PROJECT_DIR / "data" / "resources_international.json").read_text())
    check("the small verified set is present", len(blob["resources"]) >= 8)

    for row in blob["resources"]:
        name = row.get("name")
        check(f"{name!r} records the page that was opened", bool(row.get("source_url")))
        check(f"{name!r} is dated", bool(row.get("verified_at")))
        check(f"{name!r} has a country or GLOBAL", bool(row.get("region")))
        check(f"{name!r} has a way to reach it",
              bool(row.get("phone") or row.get("url") or row.get("text_line")))
        try:
            _dt.date.fromisoformat(row["verified_at"])
        except Exception:
            check(f"{name!r} date is ISO format", False, row.get("verified_at"))

    names = {r["name"] for r in blob["resources"]}
    # Each of these was excluded for a specific, recorded reason. Re-adding one without
    # resolving that reason is the failure this guards.
    for excluded, why in (
        ("13YARN", "its own page prints two different numbers for itself"),
        # Narrow on purpose: Dublin Rape Crisis Centre IS verified and belongs. The
        # one excluded is Rape Crisis England & Wales, whose site would not load.
        ("Rape Crisis England", "its site returned HTTP 525 and was never read"),
        ("WAVE", "an umbrella network's office, not a crisis line"),
    ):
        check(f"{excluded} stays out — {why}",
              not any(excluded.lower() in n.lower() for n in names))


def test_the_international_file_invents_nothing() -> None:
    """Empty on purpose, and it has to stay that way until somebody verifies entries.

    Emergency numbers differ (999, 112, 000, 119), helplines change, and some widely
    listed online no longer operate. Being confidently wrong here costs more than being
    empty.
    """
    path = PROJECT_DIR / "data" / "resources_international.json"
    check("the file exists as the place for them", path.is_file())
    blob = json.loads(path.read_text())
    for row in blob["resources"]:
        check(f"{row.get('name')!r} records the source that was opened",
              bool(row.get("source_url")),
              "every international entry must name the organisation's own page")
        check(f"{row.get('name')!r} declares a region", bool(row.get("region")))
        check(f"{row.get('name')!r} is verified", bool(row.get("verified_at")))


def test_verification_survives_a_database_rebuild() -> None:
    """The signature belongs in the committed pack, not in a disposable database.

    Until 2026-11-11 ``verify_research ok`` wrote only to SQLite — and CLAUDE.md tells
    you to delete that database on every schema change. Adding ``entry_themes`` did
    exactly that and took eighteen human verifications with it. The pack now carries
    ``verification_status`` / ``verified_at`` / ``verified_by``, and the source gate
    still applies on the way in, so a file cannot approve its own work.
    """
    import tempfile as _tf

    blob = json.loads(
        (PROJECT_DIR / "data" / "research" / "behavioral_indicators.json").read_text())
    verified = [n for n in blob["notes"] if n.get("verification_status") == "verified"]
    check("the committed pack carries its verifications", len(verified) >= 18,
          f"only {len(verified)} — were they written back by `ok`?")
    for n in verified:
        check(f"{n['id']} records who signed it", bool(n.get("verified_by")))
        check(f"{n['id']} records when", bool(n.get("verified_at")))
        check(f"{n['id']} records what was opened", bool(n.get("source_url")))

    # A rebuild from the file alone restores them.
    s = Store(Path(_tf.mkdtemp()) / "rebuilt.db")
    s.load_research_pack(
        PROJECT_DIR / "data" / "research" / "behavioral_indicators.json")
    check("a fresh database reloads them as verified",
          len(s.citable_refs()) >= 17,
          f"{len(s.citable_refs())} citable after rebuild")

    # But the file still cannot approve itself against a source KRYteria will not cite.
    bad = dict(blob)
    bad["notes"] = [dict(verified[0], id="self-approved",
                         source_url="https://goop.com/wellness")]
    path = Path(_tf.mkdtemp()) / "bad.json"
    path.write_text(json.dumps(bad))
    expect_raises("a pack cannot verify itself against a bad source", StoreError,
                  Store(Path(_tf.mkdtemp()) / "g.db").load_research_pack, path)


# ---------------------------------------------------------------- criteria versioning

def test_criteria_are_versioned_not_overwritten() -> None:
    s, acct, dom = fresh()
    c1 = s.create_criterion(
        acct, value="Follow-through",
        desired_behavior="Does what they said they would do",
        why_it_matters="I stop trusting my own judgment when I let this slide",
    )
    c2 = s.revise_criterion(
        acct, c1, revision_note="Decided I was being too rigid",
        desired_behavior="Tells me when plans change",
    )

    check("revision returns a new row", c2 != c1)

    active = s.list_criteria(acct, status="active")
    check("only one active version", len(active) == 1, f"got {len(active)}")
    check("active row is the new one", active and active[0]["id"] == c2)
    check("new version is 2", active and active[0]["version"] == 2)

    all_rows = s.list_criteria(acct, status="all")
    check("both versions survive", len(all_rows) == 2, f"got {len(all_rows)}")

    old = next(r for r in all_rows if r["id"] == c1)
    check("old row is superseded", old["status"] == "superseded")
    check("old row keeps its original wording",
          old["desired_behavior"] == "Does what they said they would do")
    check("old row stamped with superseded_at", bool(old["superseded_at"]))

    lineage = s.criterion_history(acct, active[0]["lineage_id"])
    check("history is ordered oldest first",
          [r["version"] for r in lineage] == [1, 2])
    check("history shows the standard being softened",
          [r["desired_behavior"] for r in lineage]
          == ["Does what they said they would do", "Tells me when plans change"])
    check("revision note is kept", lineage[1]["revision_note"] == "Decided I was being too rigid")

    # Unchanged fields carry forward rather than blanking out.
    check("unrevised field carries forward", lineage[1]["value"] == "Follow-through")

    expect_raises("revising a superseded version is refused", StoreError,
                  s.revise_criterion, acct, c1, value="x")
    expect_raises("unknown field is refused", StoreError,
                  s.revise_criterion, acct, c2, nonsense="x")


# ---------------------------------------------------------------- pattern evidence

def test_pattern_requires_evidence() -> None:
    s, acct, dom = fresh()
    expect_raises("a pattern with no evidence is refused", StoreError,
                  s.save_pattern, acct, domain_id=dom, kind="recurring_unmet_need",
                  statement="They never follow through", evidence=[])

    expect_raises("evidence without entry ids is refused", StoreError,
                  s.save_pattern, acct, domain_id=dom, kind="recurring_unmet_need",
                  statement="They never follow through",
                  evidence=[{"observation_id": 1}])


def test_thin_evidence_is_downgraded() -> None:
    s, acct, dom = fresh()
    e1 = s.create_entry(acct, dom, body="Said he'd call, didn't.")
    e2 = s.create_entry(acct, dom, body="Cancelled again.")

    result = s.save_pattern(
        acct, domain_id=dom, kind="recurring_unmet_need",
        statement="Follow-through has not happened",
        evidence_strength="strong",          # the model claimed it was sure
        alternatives=["He may be overwhelmed at work"],
        evidence=[{"entry_id": e1}, {"entry_id": e2}],
    )
    check("two entries is below the bar", MIN_SUPPORT > 2)
    check("thin evidence is forced to insufficient",
          result["evidence_strength"] == "insufficient")
    check("the downgrade is reported", result["downgraded"] is True)
    check("support_count is the real count", result["support_count"] == 2)

    stored = s.list_patterns(acct, status="all")[0]
    check("gap note explains what is missing", bool(stored["gap_note"]))
    check("the finding is still written, not hidden", stored["statement"].startswith("Follow"))
    check("evidence is retrievable with the finding", len(stored["evidence"]) == 2)


def test_support_count_is_counted_not_trusted() -> None:
    s, acct, dom = fresh()
    ids = [s.create_entry(acct, dom, body=f"entry {i}") for i in range(4)]
    # Same entry listed repeatedly must not inflate the count.
    result = s.save_pattern(
        acct, domain_id=dom, kind="repeated_discrepancy", statement="Repeated",
        evidence=[{"entry_id": ids[0]}] * 5,
    )
    check("duplicate entries count once", result["support_count"] == 1)
    check("one entry cannot be a pattern",
          result["evidence_strength"] == "insufficient")

    result2 = s.save_pattern(
        acct, domain_id=dom, kind="repeated_discrepancy", statement="Repeated",
        evidence_strength="moderate",
        alternatives=["Could be a stressful few weeks rather than a habit"],
        evidence=[{"entry_id": i} for i in ids[:MIN_SUPPORT]],
    )
    check("enough distinct entries holds its strength",
          result2["evidence_strength"] == "moderate")
    check("support_count matches distinct entries",
          result2["support_count"] == MIN_SUPPORT)


def test_counter_evidence_is_preserved() -> None:
    s, acct, dom = fresh()
    ids = [s.create_entry(acct, dom, body=f"entry {i}") for i in range(5)]
    result = s.save_pattern(
        acct, domain_id=dom, kind="recurring_unmet_need",
        statement="Plans get changed at short notice",
        evidence_strength="moderate",
        alternatives=["Shift work may make the notice genuinely unavoidable"],
        uncertainties=["Unclear how far ahead the plans were made"],
        evidence=[
            {"entry_id": ids[0]}, {"entry_id": ids[1]}, {"entry_id": ids[2]},
            {"entry_id": ids[3], "stance": "contradicts"},
            {"entry_id": ids[4], "stance": "contradicts"},
        ],
    )
    check("supporting entries counted", result["support_count"] == 3)
    check("contradicting entries counted separately", result["contra_count"] == 2)

    stored = s.list_patterns(acct, status="all")[0]
    check("counter-evidence is retrievable", len(stored["counter_evidence"]) == 2)
    check("counter-evidence is not mixed into support", len(stored["evidence"]) == 3)
    check("uncertainties survive", stored["uncertainties"] == [
        "Unclear how far ahead the plans were made"])
    check("alternatives survive", len(stored["alternatives"]) == 1)

    expect_raises("an unknown stance is refused", StoreError,
                  s.save_pattern, acct, domain_id=dom, kind="repeated_discrepancy",
                  statement="x", evidence=[{"entry_id": ids[0], "stance": "maybe"}])


def test_confident_findings_must_offer_an_alternative() -> None:
    s, acct, dom = fresh()
    ids = [s.create_entry(acct, dom, body=f"entry {i}") for i in range(4)]
    ev = [{"entry_id": i} for i in ids]

    for strength in ("moderate", "strong"):
        expect_raises(
            f"a '{strength}' finding with no alternative is refused", StoreError,
            s.save_pattern, acct, domain_id=dom, kind="repeated_discrepancy",
            statement="They do not care", evidence_strength=strength, evidence=ev,
        )
    expect_raises("blank alternatives do not satisfy the rule", StoreError,
                  s.save_pattern, acct, domain_id=dom, kind="repeated_discrepancy",
                  statement="x", evidence_strength="strong",
                  alternatives=["  ", ""], evidence=ev)

    ok = s.save_pattern(
        acct, domain_id=dom, kind="repeated_discrepancy", statement="A real finding",
        evidence_strength="strong", alternatives=["Another reading is possible"],
        evidence=ev,
    )
    check("a finding that admits another reading is allowed",
          ok["evidence_strength"] == "strong")

    # 'limited' is an honest, low-confidence claim and needs no alternative.
    low = s.save_pattern(acct, domain_id=dom, kind="repeated_discrepancy",
                         statement="Might be something here",
                         evidence_strength="limited", evidence=ev)
    check("a tentative finding needs no alternative",
          low["evidence_strength"] == "limited")

    expect_raises("a numeric strength is refused", StoreError,
                  s.save_pattern, acct, domain_id=dom, kind="repeated_discrepancy",
                  statement="x", evidence_strength="0.87", evidence=ev)


# ---------------------------------------------------------------- fact/interpretation

def test_observation_kinds_are_validated() -> None:
    s, acct, dom = fresh()
    e = s.create_entry(acct, dom, body="He forgot my birthday. He doesn't care.")

    expect_raises("an unknown observation kind is refused", StoreError,
                  s.save_observations, acct, e, [{"kind": "fact", "text": "x"}])
    expect_raises("a missing observation kind is refused", StoreError,
                  s.save_observations, acct, e, [{"text": "x"}])

    ids = s.save_observations(acct, e, [
        {"kind": "reported_event", "text": "He did not acknowledge her birthday."},
        {"kind": "interpretation", "text": "She reads this as not caring."},
        {"kind": "emotional_reaction", "text": "She felt dismissed."},
        {"kind": "missing_information", "text": "Whether he knew the date."},
    ])
    check("four observations stored", len(ids) == 4)

    events = s.list_observations(acct, entry_ids=[e], kinds=["reported_event"])
    check("reported events are separable", len(events) == 1)
    check("the interpretation did not become an event",
          "not caring" not in events[0]["text"])

    interps = s.list_observations(acct, entry_ids=[e], kinds=["interpretation"])
    check("interpretations are retrievable as such", len(interps) == 1)
    check("agent-extracted observations are attributed",
          interps[0]["attributed_to"] == "agent")

    blanks = s.save_observations(acct, e, [{"kind": "uncertainty", "text": "   "}])
    check("empty observation text is skipped, not stored", blanks == [])


# ---------------------------------------------------------------- postponement

def test_postponement_counting() -> None:
    s, acct, dom = fresh()
    c = s.create_criterion(acct, value="Follow-through",
                           desired_behavior="Does what they said")
    check("no postponements at the start",
          s.count_postponements(acct, criterion_id=c) == 0)
    check("no probe at the start",
          s.should_probe_postponement(acct, criterion_id=c) is False)

    for _ in range(POSTPONEMENT_PROBE_AT - 1):
        s.record_decision(acct, choice="more_time", criterion_id=c)
    check("below the threshold, no probe",
          s.should_probe_postponement(acct, criterion_id=c) is False)

    s.record_decision(acct, choice="more_time", criterion_id=c)
    check("at the threshold, the probe is allowed",
          s.should_probe_postponement(acct, criterion_id=c) is True)
    check("count is exact",
          s.count_postponements(acct, criterion_id=c) == POSTPONEMENT_PROBE_AT)

    # Other decisions are not postponements.
    other = s.create_criterion(acct, value="Honesty", desired_behavior="Tells me things")
    for choice in ("talk", "boundary", "gather_info", "reconsider", "undecided"):
        s.record_decision(acct, choice=choice, criterion_id=other)
    check("other choices do not count as postponement",
          s.count_postponements(acct, criterion_id=other) == 0)
    check("postponements are scoped per criterion",
          s.count_postponements(acct, criterion_id=c) == POSTPONEMENT_PROBE_AT)

    expect_raises("an unknown decision is refused", StoreError,
                  s.record_decision, acct, choice="dump_him")


# ---------------------------------------------------------------- entries

def test_entry_modes() -> None:
    s, acct, dom = fresh()
    expect_raises("an empty free entry is refused", StoreError,
                  s.create_entry, acct, dom, entry_mode="free", body="   ")
    expect_raises("an empty structured entry is refused", StoreError,
                  s.create_entry, acct, dom, entry_mode="structured")

    free_id = s.create_entry(acct, dom, entry_mode="free",
                             body="Post-date debrief: nice evening, but the same thing again.")
    struct_id = s.create_entry(acct, dom, entry_mode="structured",
                               what_happened="Cancelled an hour before",
                               what_expected="To be told earlier",
                               how_it_affected="Felt like an afterthought")
    check("both entry modes are accepted", free_id and struct_id)

    rows = s.list_entries(acct)
    check("both entries are listed", len(rows) == 2)
    modes = {r["entry_mode"] for r in rows}
    check("neither mode is a second-class citizen", modes == {"free", "structured"})

    found = s.list_entries(acct, search="debrief")
    check("search finds free text", len(found) == 1 and found[0]["id"] == free_id)
    found2 = s.list_entries(acct, search="afterthought")
    check("search finds structured fields", len(found2) == 1 and found2[0]["id"] == struct_id)


def test_standards_are_never_judged() -> None:
    """"Soft hands" is as valid a criterion as "Compatible relationship intentions".

    KRYteria does not rank, score, or second-guess what matters to somebody. If a future
    change adds validation that rejects a criterion for being trivial, this fails.
    """
    s, acct, dom, prof = fresh_profile()
    for value, tier in [
        ("Soft hands", "preferred"),
        ("Beautiful singing voice", "aspirational"),
        ("Compatible relationship intentions", "mandatory"),
        ("Independent identity and interests", "mandatory"),
    ]:
        cid = s.create_criterion(acct, value=value,
                                 desired_behavior=f"Shows {value.lower()}")
        s.add_criterion_to_profile(acct, prof, cid, tier=tier)
        check(f"{value!r} is accepted as written", bool(cid))

    rows = s.list_criteria(acct)
    check("all four are in the library", len(rows) == 4)
    check("the library carries no tier", "tier" not in rows[0])
    check("no score column leaked in", not any(
        k in rows[0] for k in ("score", "rating", "importance", "quality")))

    in_profile = s.list_profile_criteria(acct, prof)
    check("mandatory criteria sort first",
          [r["tier"] for r in in_profile][:2] == ["mandatory", "mandatory"])
    check("aspirational sorts last", in_profile[-1]["tier"] == "aspirational")

    expect_raises("an unknown tier is refused", StoreError,
                  s.add_criterion_to_profile, acct, prof, rows[0]["id"], tier="essential")


def test_profiles_are_independent() -> None:
    """The Jimmy G Principle as an architectural requirement, not a funny example.

    The same criterion carries its own tier in each profile, and changing one profile
    must never reach into another.
    """
    s, acct, dom = fresh()
    husband = s.create_profile(acct, "Husband KRYteria", objective="Marriage")
    ons = s.create_profile(acct, "One Night Stand KRYteria", objective="One-time")

    attraction = s.create_criterion(acct, value="Physical attraction",
                                    desired_behavior="I am drawn to him")
    kids = s.create_criterion(acct, value="Wants children",
                              desired_behavior="Wants children within a few years")

    s.add_criterion_to_profile(acct, husband, attraction, tier="preferred")
    s.add_criterion_to_profile(acct, husband, kids, tier="mandatory")
    s.add_criterion_to_profile(acct, ons, attraction, tier="mandatory")
    s.add_criterion_to_profile(acct, ons, kids, relevance="not_applicable")

    def tier_of(profile, criterion):
        return next(r["tier"] for r in s.list_profile_criteria(acct, profile)
                    if r["criterion_id"] == criterion)

    check("attraction is Preferred for a husband", tier_of(husband, attraction) == "preferred")
    check("attraction is Mandatory for a one-night stand",
          tier_of(ons, attraction) == "mandatory")
    check("one criterion, one library row", len(s.list_criteria(acct)) == 2)

    # Changing one profile must not touch the other.
    s.set_profile_tier(acct, husband, attraction, "mandatory")
    check("the edited profile changed", tier_of(husband, attraction) == "mandatory")
    check("the other profile did not", tier_of(ons, attraction) == "mandatory")
    s.set_profile_tier(acct, ons, attraction, "preferred")
    check("and it works the other way too",
          tier_of(husband, attraction) == "mandatory"
          and tier_of(ons, attraction) == "preferred")

    # Copying is explicit, and produces an independent configuration.
    casual = s.create_profile(acct, "Fuck Buddy KRYteria", objective="Ongoing casual")
    s.copy_criteria_to_profile(acct, husband, casual)
    check("copied criteria arrive", len(s.list_profile_criteria(acct, casual)) == 2)
    check("copied settings come across", tier_of(casual, attraction) == "mandatory")
    s.set_profile_tier(acct, casual, attraction, "aspirational")
    check("editing the copy does not touch the source",
          tier_of(husband, attraction) == "mandatory")
    check("provenance is recorded",
          any(r["copied_from_profile_id"] == husband
              for r in s.list_profile_criteria(acct, casual)))

    expect_raises("a profile cannot copy into itself", StoreError,
                  s.copy_criteria_to_profile, acct, husband, husband)


def test_not_applicable_is_not_fail_or_unknown() -> None:
    """Three distinct answers that a sloppy implementation would merge."""
    s, acct, dom = fresh()
    husband = s.create_profile(acct, "Husband KRYteria")
    ons = s.create_profile(acct, "One Night Stand KRYteria")
    kids = s.create_criterion(acct, value="Wants children", desired_behavior="Wants kids")
    s.add_criterion_to_profile(acct, husband, kids, tier="mandatory")
    s.add_criterion_to_profile(acct, ons, kids, relevance="not_applicable")
    p = s.upsert_person(acct, "J")

    husband_board = s.assessment_board(acct, husband, p)
    ons_board = s.assessment_board(acct, ons, p)
    check("unassessed under Husband reads unknown",
          husband_board[0]["assessment"] == "unknown")
    check("not relevant under One Night Stand reads not_applicable",
          ons_board[0]["assessment"] == "not_applicable")
    check("not_applicable is not fail", ons_board[0]["assessment"] != "fail")
    check("not_applicable is not unknown", ons_board[0]["assessment"] != "unknown")
    check("the criterion survives in the library untouched",
          len(s.list_criteria(acct)) == 1)

    # A status set under one profile never leaks into another.
    s.set_assessment(acct, husband, kids, p, "fail")
    check("Husband now fails", s.get_assessment(acct, husband, kids, p) == "fail")
    check("One Night Stand is unaffected",
          s.assessment_board(acct, ons, p)[0]["assessment"] == "not_applicable")


def test_assessment_history_is_kept() -> None:
    s, acct, dom, prof = fresh_profile()
    c = s.create_criterion(acct, value="Consistency", desired_behavior="Follows through")
    s.add_criterion_to_profile(acct, prof, c, tier="mandatory")
    p = s.upsert_person(acct, "J")

    aid = s.set_assessment(acct, prof, c, p, "unknown", origin="system_initial")
    s.set_assessment(acct, prof, c, p, "pass", explanation="Three follow-throughs")
    s.set_assessment(acct, prof, c, p, "unknown", explanation="Changed my mind")

    hist = s.assessment_history(acct, aid)
    check("every transition is kept", len(hist) == 3)
    check("transitions record what they came from",
          [h["previous_status"] for h in hist] == ["unknown", "unknown", "pass"])
    check("transitions record what they went to",
          [h["new_status"] for h in hist] == ["unknown", "pass", "unknown"])
    check("the origin is recorded", hist[0]["origin"] == "system_initial")
    check("the explanation is kept", hist[1]["explanation"] == "Three follow-throughs")


def test_agent_cannot_silently_change_an_assessment() -> None:
    """The agent proposes; the user decides. Enforced by there being two tables."""
    s, acct, dom, prof = fresh_profile()
    c = s.create_criterion(acct, value="Emotional maturity",
                           desired_behavior="Handles disagreement without hostility")
    s.add_criterion_to_profile(acct, prof, c, tier="mandatory")
    p = s.upsert_person(acct, "J", domain_id=dom)

    check("assessment starts unknown", s.get_assessment(acct, prof, c, p) == "unknown")

    pid = s.propose_assessment(acct, prof, c, p, "pass",
                               rationale="Took time to regulate, came back, apologised")
    check("the proposal does not move the status",
          s.get_assessment(acct, prof, c, p) == "unknown")
    check("the proposal is pending", len(s.list_pending_proposals(acct)) == 1)
    check("the proposal records what it would change from",
          s.list_pending_proposals(acct)[0]["current_status"] == "unknown")

    expect_raises("a proposal with no rationale is refused", StoreError,
                  s.propose_assessment, acct, prof, c, p, "fail", "   ")

    s.resolve_proposal(acct, pid, "accepted")
    check("accepting applies it", s.get_assessment(acct, prof, c, p) == "pass")
    check("no proposals left pending", s.list_pending_proposals(acct) == [])
    expect_raises("a resolved proposal cannot be resolved twice", StoreError,
                  s.resolve_proposal, acct, pid, "rejected")

    # Rejecting leaves the status alone.
    pid2 = s.propose_assessment(acct, prof, c, p, "fail",
                                rationale="One difficult evening")
    s.resolve_proposal(acct, pid2, "rejected")
    check("rejecting changes nothing", s.get_assessment(acct, prof, c, p) == "pass")

    # Editing lets the user pick a third answer.
    pid3 = s.propose_assessment(acct, prof, c, p, "fail",
                                rationale="Another difficult evening")
    s.resolve_proposal(acct, pid3, "edited", final_status="unknown")
    check("editing applies the user's choice, not the agent's",
          s.get_assessment(acct, prof, c, p) == "unknown")

    # An accepted proposal is recorded as the user's act, not the agent's.
    aid = s.set_assessment(acct, prof, c, p, "unknown")
    origins = {h["origin"] for h in s.assessment_history(acct, aid)}
    check("the history distinguishes accepted from edited proposals",
          {"user_accepted_proposal", "user_edited_proposal"} <= origins)

    expect_raises("an unknown status is refused", StoreError,
                  s.set_assessment, acct, prof, c, p, "maybe")


def test_assessment_is_per_person() -> None:
    """Same standard, two people, two answers — this is how 'am I making exceptions
    for someone I wouldn't make for anyone else' becomes answerable."""
    s, acct, dom, prof = fresh_profile()
    c = s.create_criterion(acct, value="Follow-through",
                           desired_behavior="Does what they said")
    s.add_criterion_to_profile(acct, prof, c, tier="mandatory")
    a = s.upsert_person(acct, "A", domain_id=dom)
    b = s.upsert_person(acct, "B", domain_id=dom)

    s.set_assessment(acct, prof, c, a, "pass")
    s.set_assessment(acct, prof, c, b, "fail")
    check("person A passes", s.get_assessment(acct, prof, c, a) == "pass")
    check("person B fails on the same criterion", s.get_assessment(acct, prof, c, b) == "fail")

    board = s.assessment_board(acct, prof, a)
    check("the board carries one row per criterion", len(board) == 1)
    check("the board carries the status", board[0]["assessment"] == "pass")

    s.set_assessment(acct, prof, c, a, "unknown")
    check("a status can be walked back to unknown",
          s.get_assessment(acct, prof, c, a) == "unknown")


def test_evidence_has_four_relations() -> None:
    s, acct, dom = fresh()
    c = s.create_criterion(acct, value="Emotional maturity",
                           desired_behavior="Handles disagreement well")
    e = s.create_entry(acct, dom, body="He got upset, took a few minutes, came back "
                                       "and apologised.")
    for rel in ("supporting", "contradicting", "complicating", "unrelated"):
        lid = s.link_evidence(acct, entry_id=e, criterion_id=c, relation=rel)
        check(f"{rel} is a valid relation", bool(lid))

    check("complicating survives as its own category",
          len(s.list_evidence_links(acct, criterion_id=c)) == 4)

    expect_raises("an unknown relation is refused", StoreError,
                  s.link_evidence, acct, entry_id=e, criterion_id=c, relation="bad")

    # Agent-proposed mappings wait for the user.
    pending = s.list_evidence_links(acct, resolution="pending")
    check("agent links start pending", len(pending) == 4)
    s.resolve_evidence_link(acct, pending[0]["id"], "edited", relation="complicating")
    check("an edited link takes the user's relation",
          s.list_evidence_links(acct, resolution="edited")[0]["relation"] == "complicating")

    # A user's own link needs no confirmation.
    own = s.link_evidence(acct, entry_id=e, criterion_id=c, relation="supporting",
                          proposed_by="user")
    accepted = [l for l in s.list_evidence_links(acct) if l["id"] == own]
    check("a user's own mapping is accepted immediately",
          accepted[0]["resolution"] == "accepted")


def test_retention_erases_what_was_not_asked_for() -> None:
    """The user decides what KRYteria keeps, and erasure actually erases.

    Somebody may want to keep the fact that they noticed a pattern without keeping the
    intimate 2,000-word account they wrote at 1 a.m.
    """
    s, acct, dom = fresh()
    account = s.get_account(acct)
    check("the default keeps analysis but not the original",
          account["retention"] == "analysis_only")

    # keep_all leaves everything alone.
    e1 = s.create_entry(acct, dom, body="A long private account.")
    s.save_observations(acct, e1, [{"kind": "reported_event", "text": "He was late."}])
    r1 = s.apply_retention(acct, e1, "keep_all")
    check("keep_all erases nothing", r1["original_erased"] is False)
    check("and the narrative survives", s.get_entry(acct, e1)["body"] is not None)

    # analysis_only erases the narrative, keeps what was learned from it.
    e2 = s.create_entry(acct, dom, body="Another private account, 2000 words of it.")
    s.save_observations(acct, e2, [{"kind": "reported_event", "text": "He cancelled."}])
    r2 = s.apply_retention(acct, e2, "analysis_only")
    check("analysis_only erases the original", r2["original_erased"] is True)
    check("the body is NULL, not blanked",
          s.get_entry(acct, e2)["body"] is None)
    check("the observations survive",
          len(s.list_observations(acct, entry_ids=[e2])) == 1)
    check("the entry row survives as a placeholder",
          s.get_entry(acct, e2) is not None)
    check("and records when it was erased",
          bool(s.get_entry(acct, e2)["original_erased_at"]))

    # discard takes the derived records too — an observation can be a near-quotation.
    e3 = s.create_entry(acct, dom, body="The most private one.")
    s.save_observations(acct, e3, [{"kind": "reported_event", "text": "Near-quotation."}])
    s.save_interrogation(acct, entry_id=e3, claim="He's always late.",
                         gap_kind="frequency", question="How often?")
    r3 = s.apply_retention(acct, e3, "discard")
    check("discard erases the original", r3["original_erased"] is True)
    check("and removes what was derived from it", r3["derived_removed"] >= 2)
    check("no observations are left",
          s.list_observations(acct, entry_ids=[e3]) == [])
    check("no quoted claims are left",
          s.list_interrogations(acct, entry_id=e3) == [])

    # Structured fields are erased too, not just the free-text body.
    e4 = s.create_entry(acct, dom, entry_mode="structured",
                        what_happened="Something private", what_expected="Something else")
    s.apply_retention(acct, e4, "analysis_only")
    row = s.get_entry(acct, e4)
    check("structured fields are erased as well",
          row["what_happened"] is None and row["what_expected"] is None)

    expect_raises("an unknown retention mode is refused", StoreError,
                  s.apply_retention, acct, e1, "keep_forever")
    expect_raises("retention cannot be applied to another account's entry", StoreError,
                  s.apply_retention, acct + 999, e1, "discard")

    report = s.retention_report(acct)
    check("the report counts what is actually kept",
          report["originals_erased"] == 3, f"got {report['originals_erased']}")
    check("and names the account default",
          report["default_retention"] == "analysis_only")

    # Changing the default and sweeping applies it to what was already written.
    s.set_preferences(acct, retention="analysis_only")
    e5 = s.create_entry(acct, dom, body="Written before the sweep.")
    swept = s.erase_originals(acct)
    check("the sweep erases entries that were still holding originals", swept >= 1)
    check("including the new one", s.get_entry(acct, e5)["body"] is None)
    check("but never one marked keep_all",
          s.get_entry(acct, e1)["body"] is not None)

    expect_raises("an unknown default is refused", StoreError,
                  s.set_preferences, acct, retention="whatever")


def test_store_refuses_cross_account_reach() -> None:
    """Enforced at the database layer, not only in the API.

    The API's ownership guards are the first line. These are the line that holds when
    somebody adds a route and forgets — and for this product a leak would tell one
    person that another is journalling about them.
    """
    from backend.store import NotOwned

    s, alice, alice_dom = fresh()
    bob = s.create_account("bob", "a long enough passphrase")
    bob_dom = s.create_domain(bob, "Dating", "romantic")

    a_crit = s.create_criterion(alice, value="Follow-through", desired_behavior="x")
    a_prof = s.create_profile(alice, "Boyfriend KRYteria")
    s.add_criterion_to_profile(alice, a_prof, a_crit, tier="mandatory")
    a_person = s.upsert_person(alice, "J", domain_id=alice_dom)
    a_entry = s.create_entry(alice, alice_dom, body="private")
    a_assess = s.set_assessment(alice, a_prof, a_crit, a_person, "pass")

    b_crit = s.create_criterion(bob, value="Honesty", desired_behavior="y")
    b_prof = s.create_profile(bob, "Bob's profile")

    for label, fn, args in [
        ("read her profile's criteria", s.list_profile_criteria, (bob, a_prof)),
        ("revise her criterion", s.revise_criterion, (bob, a_crit)),
        ("retire her criterion", s.retire_criterion, (bob, a_crit)),
        ("read her assessment history", s.assessment_history, (bob, a_assess)),
        ("erase her entry", s.apply_retention, (bob, a_entry, "discard")),
    ]:
        try:
            fn(*args)
        except NotOwned:
            check(f"bob cannot {label}", True)
        except Exception as e:
            check(f"bob cannot {label}", False, f"raised {type(e).__name__}: {e}")
        else:
            check(f"bob cannot {label}", False, "it succeeded")

    expect_raises("bob cannot add her criterion to his profile", StoreError,
                  s.add_criterion_to_profile, bob, b_prof, a_crit)
    expect_raises("bob cannot add his criterion to her profile", StoreError,
                  s.add_criterion_to_profile, bob, a_prof, b_crit)
    expect_raises("bob cannot retier her profile", StoreError,
                  s.set_profile_tier, bob, a_prof, a_crit, "preferred")
    expect_raises("bob cannot copy from her profile", StoreError,
                  s.copy_criteria_to_profile, bob, a_prof, b_prof)

    check("her assessment is untouched",
          s.get_assessment(alice, a_prof, a_crit, a_person) == "pass")
    check("her entry is untouched", s.get_entry(alice, a_entry)["body"] == "private")
    check("bob reading her assessment gets unknown, not her answer",
          s.get_assessment(bob, a_prof, a_crit, a_person) == "unknown")


def test_sql_constraints_match_the_python_constants() -> None:
    """A CHECK constraint duplicated across tables must not drift from the code.

    The `reflections.tone_mode` CHECK was left on the old gentle/direct/no_bs values when
    the triad became Clarity/Tough Love, and nothing caught it until a brain dump with a
    reflection returned a 500 in the browser. The column-drift guard compares columns,
    not constraints, so this is the test that closes that gap.
    """
    import re

    from backend.store import (
        ASSESSMENT_STATUSES, CHECKLIST_STATES, CONCERN_LEVELS, EVIDENCE_RELATIONS,
        GAP_KINDS, OBSERVATION_KINDS, RETENTION_MODES, SCHEMA_PATH, SOURCE_LEVELS,
        TIERS, TONE_MODES,
    )

    sql = SCHEMA_PATH.read_text(encoding="utf-8")

    def values_in(column: str) -> list[set[str]]:
        """Every CHECK over this column name, as sets of allowed values."""
        found = []
        for m in re.finditer(rf"CHECK \({re.escape(column)} IN \(([^)]*)\)\)", sql):
            found.append({v.strip().strip("'") for v in m.group(1).split(",")})
        return found

    expected = {
        "tone_mode": set(TONE_MODES),
        "tier": set(TIERS),
        "status": None,                      # reused across tables with different sets
        "retention": set(RETENTION_MODES),
        "certainty": {"stated", "inferred"},
        "relation": set(EVIDENCE_RELATIONS),
        "state": set(CHECKLIST_STATES),
        "concern_level": set(CONCERN_LEVELS),
        "gap_kind": set(GAP_KINDS),
        "kind": None,                        # likewise
        "source_level": set(SOURCE_LEVELS),
    }

    for column, allowed in expected.items():
        if allowed is None:
            continue
        constraints = values_in(column)
        check(f"schema declares a CHECK for {column}", bool(constraints))
        for i, found in enumerate(constraints):
            check(f"{column} CHECK #{i + 1} matches the Python constant",
                  found == allowed, f"sql={sorted(found)} python={sorted(allowed)}")

    # The assessment statuses appear on two tables and must agree with each other.
    status_sets = [s for s in values_in("status") if "pass" in s]
    for i, s in enumerate(status_sets):
        check(f"assessment status CHECK #{i + 1} matches the constant",
              s == set(ASSESSMENT_STATUSES), f"sql={sorted(s)}")

    kinds = [s for s in values_in("kind") if "reported_event" in s]
    for s in kinds:
        check("observation kind CHECK matches the constant",
              s == set(OBSERVATION_KINDS), f"sql={sorted(s)}")


def test_stale_database_fails_with_an_answer() -> None:
    """A database predating a column change must not fail later with 'no such column'.

    ``CREATE TABLE IF NOT EXISTS`` silently leaves an existing table alone, so a schema
    change does not reach a database that already exists. This caught Christine on
    2026-11-08 after the research_notes rewrite, and would catch a grader after any pull.
    """
    import sqlite3

    db = Path(tempfile.mkdtemp()) / "stale.db"
    conn = sqlite3.connect(db)
    # A plausible older shape: the table exists, but without the columns added later.
    conn.executescript(
        "CREATE TABLE research_notes (id INTEGER PRIMARY KEY, area TEXT NOT NULL,"
        " finding TEXT NOT NULL, citation TEXT NOT NULL, caveat TEXT,"
        " created_at TEXT NOT NULL);"
        "CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
    )
    conn.close()

    try:
        Store(db)
    except StoreError as e:
        message = str(e)
        check("a stale database is refused at open time", True)
        # Names columns, not a specific one — which column sorts first changes as the
        # schema grows, and the test should not break every time it does.
        check("the message names the missing columns", "research_notes." in message)
        check("it gives the exact command to fix it", "seed_demo" in message)
        check("it says what is lost", "rebuilds the demo account" in message)
        check("and warns about real data first", "export" in message.lower())
    else:
        check("a stale database is refused at open time", False, "opened without error")

    # A stamp alone must not satisfy the check — the shape is what matters.
    conn = sqlite3.connect(db)
    from backend.store import SCHEMA_VERSION
    conn.execute("INSERT OR REPLACE INTO schema_meta VALUES ('version', ?)",
                 (SCHEMA_VERSION,))
    conn.commit()
    conn.close()
    expect_raises("a current version stamp does not excuse a wrong shape", StoreError,
                  Store, db)

    fresh_db = Path(tempfile.mkdtemp()) / "fresh.db"
    Store(fresh_db)
    Store(fresh_db)
    check("a fresh database opens and re-opens cleanly", True)


def test_unverified_research_is_invisible_and_uncitable() -> None:
    """The defence against a fabricated citation.

    Requiring a non-empty citation string only guarantees the model wrote something, and
    a model told to cite always writes something. Requiring the ref to resolve to a
    VERIFIED row makes fabrication impossible rather than discouraged.
    """
    s, acct, dom = fresh()
    pack = PROJECT_DIR / "data" / "research" / "behavioral_indicators.json"
    result = s.load_research_pack(pack)
    check("the curated pack loads", result["added"] >= 15, f"got {result['added']}")

    # Since the pack carries its own verifications, a load restores the signed ones —
    # and anything NOT signed in the file stays invisible, which is the rule that
    # matters. `reis-shaver-responsiveness` is the live example: a real entry, a real
    # source opened, and still pending because that source did not settle the claim.
    everything = s.list_research_notes(include_pending=True, include_safety_adjacent=True)
    pending = [n for n in everything if not n["verified_at"]]
    check("unsigned entries stay pending on load", bool(pending))
    check("and are invisible to the agents",
          not any(n["ref"] in {p["ref"] for p in pending}
                  for n in s.list_research_notes()))
    check("but the entries are there", len(everything) == result["added"])
    check("every entry has a caveat", all(n["caveat"].strip() for n in everything))
    check("every entry has a citation", all(n["citation"].strip() for n in everything))
    check("the high-risk ones carry a do_not list",
          all(n["do_not"] for n in everything if "attachment" in n["ref"]))

    c = s.create_criterion(acct, value="Emotional maturity", desired_behavior="x")
    e = s.create_entry(acct, dom, body="x")

    # An invented ref cannot get through, however plausible it looks.
    expect_raises("a citation that resolves to nothing is refused", StoreError,
                  s.link_evidence, acct, entry_id=e, criterion_id=c,
                  relation="supporting", source_level="research_informed",
                  research_ref="Gottman, J. M. (1994), p. 42")
    still_pending = pending[0]["ref"]
    expect_raises(f"a real-but-pending ref ({still_pending}) is still refused", StoreError,
                  s.link_evidence, acct, entry_id=e, criterion_id=c,
                  relation="supporting", source_level="research_informed",
                  research_ref=still_pending)
    expect_raises("an indicator citing a pending ref is refused", StoreError,
                  s.save_checklist_items, acct, c,
                  [{"text": "Responds to small bids", "source_level": "research_informed",
                    "research_ref": still_pending}])

    # Verification requires that somebody actually opened something.
    expect_raises("verifying without a source is refused", StoreError,
                  s.verify_research_note, "gottman-bids", source_url="  ",
                  verified_by="christine")
    expect_raises("verifying an unknown ref is refused", StoreError,
                  s.verify_research_note, "not-a-real-ref",
                  source_url="https://doi.org/10.2307/2092623", verified_by="christine")

    s.verify_research_note("gottman-bids", source_url="https://pubmed.ncbi.nlm.nih.gov/3572722/",
                           verified_by="christine")
    check("a verified entry becomes citable", "gottman-bids" in s.citable_refs())
    check("and becomes visible to agents",
          any(n["ref"] == "gottman-bids" for n in s.list_research_notes()))
    check("its caveat travels with it",
          s.list_research_notes()[0]["caveat"].strip() != "")

    lid = s.link_evidence(acct, entry_id=e, criterion_id=c, relation="supporting",
                          source_level="research_informed", research_ref="gottman-bids")
    check("a verified citation is accepted", bool(lid))

    # Safety-adjacent findings never reach the criteria or evidence agents.
    s.verify_research_note("stark-coercive-control", source_url="https://libcat.simmons.edu/Record/b1408707/",
                           verified_by="christine")
    check("a safety-adjacent entry stays hidden from the default view",
          not any(n["ref"] == "stark-coercive-control" for n in s.list_research_notes()))
    check("but is reachable when explicitly asked for",
          any(n["ref"] == "stark-coercive-control"
              for n in s.list_research_notes(include_safety_adjacent=True)))

    # Reloading the pack refreshes PENDING rows — that is how a corrected citation
    # reaches the database — but must never touch one a human signed off on, because the
    # approval was given for specific wording.
    #
    # Since 2026-11-11 the pack carries its own verifications, so most rows arrive
    # already signed and `kept_verified` counts them. What this still has to prove is
    # that a signature made IN THIS DATABASE is not overwritten by a reload.
    before = s.load_research_pack(pack)
    check("reloading leaves signed rows alone", before["kept_verified"] >= 2,
          f"got {before['kept_verified']}")
    check("a locally verified entry is still citable", "gottman-bids" in s.citable_refs())
    signed_here = next(n for n in s.list_research_notes(include_safety_adjacent=True)
                       if n["ref"] == "gottman-bids")
    check("and the local signature survived the reload, not the pack's",
          signed_here["verified_by"] == "christine", str(signed_here["verified_by"]))
    check("the one pending entry stays pending",
          "reis-shaver-responsiveness" not in s.citable_refs())

    expect_raises("a note with no caveat is refused", StoreError,
                  s.add_research_note, ref="x", area="attachment", finding="f",
                  citation="c", caveat="   ")
    expect_raises("a note marked verified with no source is refused", StoreError,
                  s.add_research_note, ref="y", area="attachment", finding="f",
                  citation="c", caveat="k", verified_at="2026-11-08")


def test_only_reputable_sources_are_accepted() -> None:
    """Christine's rule: .gov, .edu, published papers. Nothing like Goop.

    An allowlist rather than a blocklist, because a blocklist is a list of the bad sites
    somebody already thought of and the one that matters is the one nobody listed.
    """
    from backend.sources import UnacceptableSource, check_source, is_acceptable

    for good in [
        "https://pubmed.ncbi.nlm.nih.gov/3572722/",
        "https://doi.org/10.2307/2092623",
        "https://pages.ucsd.edu/~cmckenzie/paper.pdf",
        "https://libcat.library.tamu.edu/Record/in00002670224",
        "https://search.worldcat.org/oclc/4596140",
        "https://www.guilford.com/books/Handbook/",
        "https://journals.sagepub.com/doi/10.1177/0265407595124001",
        "https://www.cambridge.org/core/books/x",
        "https://www.who.int/publications/x",
    ]:
        check(f"accepts {good.split('/')[2]}", is_acceptable(good), good)

    for bad, why in [
        ("https://goop.com/wellness/relationships/", "a lifestyle brand"),
        ("https://en.wikipedia.org/wiki/John_Gottman", "an encyclopaedia"),
        ("https://www.psychologytoday.com/us/blog/x", "popular psychology"),
        ("https://www.gwern.net/doc/psychology/1977-ross.pdf", "a personal site"),
        ("https://www.scribd.com/document/123", "an upload"),
        ("https://www.researchgate.net/publication/123", "an author upload"),
        ("https://medium.com/@someone/attachment-styles", "a blog"),
        ("https://www.goodreads.com/book/show/123", "a bookseller"),
        ("https://somecoach.com/blog/red-flags", "an unknown site"),
        ("ftp://example.edu/paper.pdf", "not a web address"),
        ("", "empty"),
    ]:
        check(f"refuses {why}", not is_acceptable(bad), bad)

    # academia.edu is why a naive .edu suffix test is not enough — the .edu belongs to
    # the company, not to a university.
    check("refuses academia.edu despite the .edu",
          not is_acceptable("https://www.academia.edu/9549293/"))

    # A refusal says why, so somebody can tell a missing publisher from a bad source.
    try:
        check_source("https://goop.com/x")
    except UnacceptableSource as e:
        check("the refusal names the problem", "lifestyle brand" in str(e))
    try:
        check_source("https://some-journal-we-forgot.org/x")
    except UnacceptableSource as e:
        check("an unknown host is told how to be added",
              "add it to backend/sources.py" in str(e))


def test_academic_country_domains_are_a_pattern_not_a_list() -> None:
    """Universities outside the US sit under ``.ac.<cc>`` and ``.edu.<cc>``.

    This started as an enumerated list — ``.ac.uk``, ``.edu.au``, ``.ac.nz`` and a few
    more — and was generalised on 2026-11-11 when a Kenyan university's catalogue record
    (``.ac.ke``) turned out to be the only qualifying source for one entry. Adding one
    country at a time is how an allowlist decays into something people route around, so
    the shape is the rule.

    The shape is strict on purpose: a two-letter country code only, so a ``.edu.com``
    lookalike cannot walk in behind it.
    """
    from backend.sources import is_acceptable

    for good in [
        "https://vufind.daystar.ac.ke/Record/0000047085",     # Kenya
        "https://www.lib.cam.ac.uk/record/42",                 # United Kingdom
        "https://library.sydney.edu.au/record/42",             # Australia
        "https://catalogue.auckland.ac.nz/record/42",          # New Zealand
        "https://opac.lib.u-tokyo.ac.jp/record/42",            # Japan
        "https://library.up.ac.za/record/42",                  # South Africa
        "https://catalogue.iitb.ac.in/record/42",              # India
    ]:
        check(f"accepts the academic domain {good.split('/')[2]}", is_acceptable(good), good)

    for bad, why in [
        ("https://thing.edu.com/fake", "a .com wearing an edu label"),
        ("https://notes.ac.xyz/fake", "a novelty TLD, not a country code"),
        ("https://blog.edu.technology/fake", "a long TLD behind an edu label"),
        ("https://acme.ac/fake", "a bare .ac domain, which is Ascension Island"),
    ]:
        check(f"refuses {why}", not is_acceptable(bad), bad)


def test_verification_requires_a_reputable_source() -> None:
    """The gate is on the door into the citable set, not on a style guide."""
    s, acct, _ = fresh()
    s.load_research_pack(PROJECT_DIR / "data" / "research" / "behavioral_indicators.json")

    # Use an entry that is genuinely still pending, so "it did not become citable"
    # means the refusal held rather than that it was already signed in the pack.
    target = next(n["ref"] for n in s.list_research_notes(
        include_pending=True, include_safety_adjacent=True) if not n["verified_at"])

    expect_raises("a wellness site cannot verify a note", StoreError,
                  s.verify_research_note, target,
                  source_url="https://goop.com/conscious-uncoupling",
                  verified_by="someone")
    expect_raises("nor can an encyclopaedia", StoreError,
                  s.verify_research_note, target,
                  source_url="https://en.wikipedia.org/wiki/John_Gottman",
                  verified_by="someone")
    check("and it is still not citable", target not in s.citable_refs())

    s.verify_research_note("gottman-bids",
                           source_url="https://catalog.lib.msu.edu/Record/x",
                           verified_by="christine")
    check("a library catalogue works", "gottman-bids" in s.citable_refs())

    # A pack cannot mark its own work verified against a source we would not cite.
    expect_raises("a pack cannot smuggle in a bad source", StoreError,
                  s.add_research_note, ref="smuggled", area="attachment",
                  finding="f", citation="c", caveat="k",
                  verified_at="2026-11-09", source_url="https://goop.com/x")


def test_research_claims_must_cite() -> None:
    s, acct, dom = fresh()
    c = s.create_criterion(acct, value="Emotional maturity", desired_behavior="x")
    e = s.create_entry(acct, dom, body="x")

    expect_raises("a research-backed link with no citation is refused", StoreError,
                  s.link_evidence, acct, entry_id=e, criterion_id=c,
                  relation="supporting", source_level="established_research")
    expect_raises("a research-informed indicator with no citation is refused", StoreError,
                  s.save_checklist_items, acct, c,
                  [{"text": "Takes responsibility", "source_level": "research_informed"}])

    # Free-text citations no longer pass. A reference the agent composed is exactly what
    # a fabricated one looks like, so it has to resolve to a verified row instead.
    expect_raises("a plausible free-text citation is refused", StoreError,
                  s.save_checklist_items, acct, c,
                  [{"text": "Can disagree without becoming contemptuous",
                    "source_level": "research_informed",
                    "research_ref": "Gottman, contempt research"}])

    s.load_research_pack(PROJECT_DIR / "data" / "research" / "behavioral_indicators.json")
    s.verify_research_note("gottman-four-horsemen", source_url="https://catalog.lib.msu.edu/Record/x",
                           verified_by="tester")

    ok = s.save_checklist_items(acct, c, [
        {"text": "Can disagree without becoming contemptuous or hostile",
         "source_level": "research_informed", "research_ref": "gottman-four-horsemen"},
        {"text": "Takes responsibility for their actions",
         "source_level": "agent_hypothesis"},
    ])
    check("an indicator citing a verified entry is stored", len(ok) == 2)
    items = s.list_checklist(acct, c)
    check("the epistemic level travels with the indicator",
          {i["source_level"] for i in items} ==
          {"research_informed", "agent_hypothesis"})
    check("a hypothesis needs no citation", any(
        i["research_ref"] is None for i in items))
    check("the cited one carries the resolvable ref",
          any(i["research_ref"] == "gottman-four-horsemen" for i in items))

    expect_raises("a note with no citation is refused", StoreError,
                  s.add_research_note, ref="z", area="attachment", finding="x",
                  citation="  ", caveat="k")


def test_ticking_a_box_does_not_set_pass() -> None:
    """The rule the UI states and the schema enforces: checking an item records an
    observation; it does not establish that the criterion passes."""
    s, acct, dom, prof = fresh_profile()
    c = s.create_criterion(acct, value="Emotional maturity", desired_behavior="x")
    s.add_criterion_to_profile(acct, prof, c, tier="mandatory")
    p = s.upsert_person(acct, "J", domain_id=dom)
    items = s.save_checklist_items(acct, c, [
        {"text": f"Indicator {i}", "source_level": "agent_hypothesis"} for i in range(6)
    ], profile_id=prof)

    for item in items:
        s.record_checklist_observation(acct, item, person_id=p)

    check("every box ticked", len(items) == 6)
    check("the criterion is still unknown", s.get_assessment(acct, prof, c, p) == "unknown")

    board = s.list_checklist(acct, c, profile_id=prof, person_id=p)
    check("observations are counted and shown",
          all(i["times_observed"] == 1 for i in board))
    check("there is no pass flag on an indicator",
          not any("passes" in i for i in board))

    # Four states, because "never had the chance to see" is not "looked and it wasn't
    # there" — merging them turns absence of evidence into evidence of absence.
    s.record_checklist_observation(acct, items[0], person_id=p, state="no_opportunity")
    s.record_checklist_observation(acct, items[1], person_id=p, state="contradicted")
    board2 = s.list_checklist(acct, c, profile_id=prof, person_id=p)
    check("no_opportunity is counted separately", board2[0]["no_opportunity"] == 1)
    check("contradicted is counted separately", board2[1]["times_contradicted"] == 1)
    check("a contradicted indicator still shows what was observed",
          board2[1]["times_observed"] == 1)
    check("the criterion is STILL unknown after all of that",
          s.get_assessment(acct, prof, c, p) == "unknown")

    expect_raises("an unknown checklist state is refused", StoreError,
                  s.record_checklist_observation, acct, items[0], state="maybe")


# ---------------------------------------------------------------- safety

def _seed_resources(s: Store) -> None:
    blob = json.loads((PROJECT_DIR / "data" / "resources_us.json").read_text())
    s.seed_resources(blob["resources"])


def test_resources_are_curated_never_invented() -> None:
    s, acct, _ = fresh()
    _seed_resources(s)

    all_res = s.list_resources(region="US")
    # Not pinned to an exact count: the set grows as entries are verified, and a test
    # that breaks every time somebody adds a checked resource trains people to edit the
    # test rather than read it.
    check("the directory loaded", len(all_res) >= 4, f"got {len(all_res)}")
    check("emergency services sort first", all_res[0]["kind"] == "emergency")
    check("every resource carries a verification date",
          all(r["verified_at"] for r in all_res))
    check("every resource has a way to reach it",
          all(r["phone"] or r["url"] or r["text_line"] for r in all_res))

    sexual = s.list_resources(region="US", category="sexual")
    check("category filtering works", any("RAINN" in r["name"] for r in sexual))
    check("a crisis line is not offered for an unrelated concern",
          not any("988" in r["name"] for r in sexual))

    # A region with no curated entries returns nothing — and nothing is the honest answer.
    check("an unknown region yields no resources, not a guess",
          s.list_resources(region="XX") == [])

    expect_raises("an unverified resource is refused", StoreError,
                  s.seed_resources, [{"name": "Made Up Line", "kind": "confidential_support",
                                      "phone": "555-0100"}])
    expect_raises("a resource with no contact route is refused", StoreError,
                  s.seed_resources, [{"name": "Nowhere", "kind": "information",
                                      "verified_at": "2026-11-07"}])


def test_declining_resources_is_respected() -> None:
    """Offering support and forcing support are different things.

    Being told "support is available" for the fourth time after saying no teaches
    somebody that telling the app something hard makes it stop being able to talk to them.
    """
    s, acct, _ = fresh()
    _seed_resources(s)

    check("resources are offered by default",
          s.should_offer_resources(acct, "disclosure") is True)

    offer = s.record_resource_offer(acct, [1, 2], "disclosure")
    s.respond_to_offer(acct, offer, "declined")

    check("a decline stops unsolicited re-offering at that level",
          s.should_offer_resources(acct, "disclosure") is False)
    check("and at lower levels too",
          s.should_offer_resources(acct, "potential") is False)

    # The crucial exception.
    check("IMMEDIATE DANGER still surfaces resources after a decline",
          s.should_offer_resources(acct, "immediate_danger") is True)

    expect_raises("an unknown concern level is refused", StoreError,
                  s.should_offer_resources, acct, "a bit worrying")


def test_resource_preference_is_honoured() -> None:
    s, acct, _ = fresh()
    _seed_resources(s)

    s.set_preferences(acct, resource_offering="on_request")
    check("on_request suppresses unsolicited offers at disclosure",
          s.should_offer_resources(acct, "disclosure") is False)
    check("on_request suppresses them at pattern level too",
          s.should_offer_resources(acct, "pattern") is False)
    check("but immediate danger still gets through",
          s.should_offer_resources(acct, "immediate_danger") is True)

    s.set_preferences(acct, resource_offering="suppressed")
    check("suppressed still does not disable immediate danger",
          s.should_offer_resources(acct, "immediate_danger") is True)

    s.set_preferences(acct, resource_offering="proactive")
    check("the user can turn offering back on",
          s.should_offer_resources(acct, "disclosure") is True)

    expect_raises("an unknown preference is refused", StoreError,
                  s.set_preferences, acct, resource_offering="never_ever")


def test_safety_layer_is_profile_independent() -> None:
    """A user never has to list safety as a criterion before the app notices.

    log_safety_event deliberately takes no profile_id. If one is ever added, this fails.
    """
    import inspect
    sig = inspect.signature(Store.log_safety_event)
    check("log_safety_event takes no profile argument",
          "profile_id" not in sig.parameters)

    s, acct, dom = fresh()
    # No profile exists, no criteria exist, nothing is marked Mandatory.
    e = s.create_entry(acct, dom, body="He grabbed my arm so I couldn't leave.")
    sid = s.log_safety_event(
        account_id=acct, entry_id=e, trigger="physical_restraint",
        category="physical", concern_level="disclosure", action="halt_and_route",
    )
    check("a safety event is recorded with no profile at all", bool(sid))

    events = s.list_safety_events(acct)
    check("the event is retrievable", len(events) == 1)
    check("the category is kept", events[0]["category"] == "physical")
    check("the concern level is kept", events[0]["concern_level"] == "disclosure")

    expect_raises("an unknown category is refused", StoreError,
                  s.log_safety_event, account_id=acct, trigger="x", action="y",
                  category="bad_vibes")
    expect_raises("an unknown concern level is refused", StoreError,
                  s.log_safety_event, account_id=acct, trigger="x", action="y",
                  concern_level="quite_bad")


def test_inference_must_be_hedged() -> None:
    """Infer, but don't presume.

    The agent may read between the lines — a user should not have to name a behaviour
    before the app can help them look at it — but a reading is marked as a reading.
    """
    s, acct, dom = fresh()
    e = s.create_entry(
        acct, dom,
        body="He kept asking why I didn't want to stay and said I was making him feel "
             "like he wasn't good enough. I stayed so there wouldn't be another argument.",
    )

    expect_raises("an unhedged inference is refused", StoreError,
                  s.save_observations, acct, e,
                  [{"kind": "interpretation", "text": "She felt pressured",
                    "certainty": "inferred"}])

    ids = s.save_observations(acct, e, [
        {"kind": "reported_event",
         "text": "He repeatedly questioned her decision to leave.",
         "certainty": "stated"},
        {"kind": "reported_event",
         "text": "She stayed rather than have another argument.",
         "certainty": "stated"},
        {"kind": "interpretation",
         "text": "She changed her decision to avoid conflict.",
         "certainty": "inferred",
         "hedge": "It sounds like you felt pressured to change your mind. Is that right?"},
    ])
    check("stated and inferred observations coexist", len(ids) == 3)

    rows = s.list_observations(acct, entry_ids=[e])
    stated = [r for r in rows if r["certainty"] == "stated"]
    inferred = [r for r in rows if r["certainty"] == "inferred"]
    check("what she described is marked stated", len(stated) == 2)
    check("what the agent read into it is marked inferred", len(inferred) == 1)
    check("the inference carries its hedge", bool(inferred[0]["hedge"]))
    check("the hedge invites correction", "?" in inferred[0]["hedge"])

    expect_raises("an unknown certainty is refused", StoreError,
                  s.save_observations, acct, e,
                  [{"kind": "interpretation", "text": "x", "certainty": "pretty sure"}])


def test_people_are_aliases() -> None:
    s, acct, dom = fresh()
    e = s.create_entry(acct, dom, body="Dinner", people=["J", "J", "  "])
    full = s.get_entry(acct, e)
    check("aliases are de-duplicated", full["people"] == ["J"])
    check("blank aliases are dropped", len(full["people"]) == 1)


# ---------------------------------------------------------------- deletion + export

def test_delete_removes_everything() -> None:
    s, acct, dom = fresh()
    e = s.create_entry(acct, dom, body="something personal")
    s.save_observations(acct, e, [{"kind": "reported_event", "text": "x"}])
    c = s.create_criterion(acct, value="v", desired_behavior="d")
    s.record_decision(acct, choice="more_time", criterion_id=c)
    s.save_pattern(acct, domain_id=dom, kind="recurring_unmet_need", statement="p",
                   evidence=[{"entry_id": e}])

    s.delete_account(acct)

    with s.read() as conn:
        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("accounts", "entries", "observations", "criteria",
                      "decisions", "patterns", "pattern_evidence", "people", "domains")
        }
    check("delete removes every trace",
          all(v == 0 for v in counts.values()),
          f"left behind: {[t for t, v in counts.items() if v]}")


def test_export_omits_the_hash() -> None:
    s, acct, dom = fresh()
    s.create_entry(acct, dom, body="x")
    blob = s.export_account(acct)
    check("export carries the account", blob["account"]["handle"] == "tester")
    check("export omits the passphrase hash", "passphrase_hash" not in blob["account"])
    check("export carries entries", len(blob["entries"]) == 1)
    flat = repr(blob)
    check("no hash material anywhere in the export", "stub$" not in flat)


def test_auth_round_trip() -> None:
    s, acct, _ = fresh()
    check("correct passphrase verifies",
          s.verify_account("tester", "a-long-enough-passphrase") == acct)
    check("wrong passphrase is refused",
          s.verify_account("tester", "wrong") is None)
    check("unknown handle is refused",
          s.verify_account("nobody", "a-long-enough-passphrase") is None)


# ---------------------------------------------------------------- run log

def test_run_log_totals() -> None:
    s, acct, _ = fresh()
    run = s.start_run(acct, "journal_entry")
    s.log_step(acct, run, 1, "evidence", input_tokens=1000, cached_input_tokens=800,
               output_tokens=200, estimated_cost_usd=0.0012, model_name="gpt-6-luna",
               tool_calls=["save_observations"])
    s.log_step(acct, run, 2, "pattern", input_tokens=1500, cached_input_tokens=1200,
               output_tokens=300, estimated_cost_usd=0.0018, model_name="gpt-6-luna")
    s.finish_run(acct, run, "ok")

    trace = s.get_run(acct, run)
    check("trace has both steps", len(trace["steps"]) == 2)
    check("trace totals input tokens", trace["input_tokens"] == 2500)
    check("trace totals cached tokens", trace["cached_input_tokens"] == 2000)
    check("trace totals output tokens", trace["output_tokens"] == 500)
    check("trace totals cost", abs(trace["cost_usd"] - 0.003) < 1e-9)
    check("cost is flagged as estimated", trace["cost_is_estimated"] is True)
    check("the billed model is recorded", trace["steps"][0]["model_name"] == "gpt-6-luna")
    check("tool calls survive the round trip",
          trace["steps"][0]["tool_calls"] == ["save_observations"])
    check("run is marked ok", trace["status"] == "ok")


def test_unreported_cache_is_unknown_not_zero() -> None:
    """'The provider didn't tell us' and 'the cache was cold' are different facts.

    Merging them understates cache hits and overstates cost, and a tokenomics section
    built on that is wrong in a way nobody reading it can see.
    """
    s, acct, _ = fresh()
    run = s.start_run(acct, "analysis")
    s.log_step(acct, run, 1, "pattern", input_tokens=1000, output_tokens=100)  # no cache reported
    trace = s.get_run(acct, run)
    check("unreported cache is None, not 0", trace["cached_input_tokens"] is None)
    check("the gap is flagged", trace["cached_tokens_reported"] is False)
    check("the raw step is NULL too", trace["steps"][0]["cached_input_tokens"] is None)

    run2 = s.start_run(acct, "analysis")
    s.log_step(acct, run2, 1, "pattern", input_tokens=1000, cached_input_tokens=0,
               output_tokens=100)
    trace2 = s.get_run(acct, run2)
    check("a genuine zero is recorded as zero", trace2["cached_input_tokens"] == 0)
    check("a genuine zero counts as reported", trace2["cached_tokens_reported"] is True)


def test_simulated_steps_are_excluded_from_cost() -> None:
    """Demo mode must never contaminate a measured cost figure."""
    s, acct, _ = fresh()
    run = s.start_run(acct, "analysis")
    s.log_step(acct, run, 1, "pattern", input_tokens=1000, output_tokens=100,
               estimated_cost_usd=0.002, model_name="gpt-6-luna")
    s.log_step(acct, run, 2, "reflection", input_tokens=9999, output_tokens=9999,
               estimated_cost_usd=99.0, is_simulated=True, model_name="demo")
    trace = s.get_run(acct, run)
    check("simulated tokens are excluded", trace["input_tokens"] == 1000)
    check("simulated cost is excluded", abs(trace["cost_usd"] - 0.002) < 1e-9)
    check("simulated steps are still visible in the trace", len(trace["steps"]) == 2)
    check("simulated steps are counted and labelled", trace["simulated_steps"] == 1)


def test_usage_accumulates() -> None:
    s, acct, _ = fresh()
    s.add_usage(acct, calls=1, input_tokens=100, output_tokens=50, cost_usd=0.001)
    s.add_usage(acct, calls=1, input_tokens=200, output_tokens=60, cost_usd=0.002)
    today = s.usage_today(acct)
    check("calls accumulate", today["calls"] == 2)
    check("input tokens accumulate", today["input_tokens"] == 300)
    check("cost accumulates", abs(today["cost_usd"] - 0.003) < 1e-9)
    glob = s.usage_all_accounts_today()
    check("global usage sees the account", glob["input_tokens"] == 300)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{PASSED} passed, {len(FAILED)} failed  ({len(tests)} test functions)")
    for f in FAILED:
        print(f"  FAIL  {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
