#!/usr/bin/env python3
"""API tests. Free — demo mode, no API key, no network, no live model call.

The most important test in this file is ``test_data_isolation``: two accounts, and one
trying to reach the other's rows every way the API allows. A journalling app that leaks
between users has no business existing, so that one runs first alphabetically and is
checked hardest.

    PYDANTIC_AI_NO_BANNER=1 .venv/bin/python tests/test_api.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

# Must be set before the app imports: demo mode needs no key, and a per-run database
# keeps these tests from touching anything real.
os.environ["KRYTERIA_MODE"] = "demo"
os.environ["KRYTERIA_DB_PATH"] = str(Path(tempfile.mkdtemp()) / f"api_{time.time()}.db")
os.environ["KRYTERIA_SECRET_KEY"] = "test-key-not-a-secret"

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    print("SKIP: fastapi/httpx not installed. Create the venv and install requirements.")
    raise SystemExit(0)

from backend.main import app  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{label}{(' — ' + detail) if detail else ''}")


def new_client(handle: str) -> TestClient:
    # This suite creates dozens of accounts in a second, which is precisely the shape
    # `throttle.check_new_account` exists to refuse. Stand that one bound down here so
    # that tests about profiles and journals are not gated on a rate limiter; the bound
    # itself is exercised deliberately in
    # `test_account_creation_is_bounded_for_the_application_as_a_whole`. Narrow on
    # purpose — clearing all throttle state would disarm the brute-force tests too.
    from backend import throttle
    throttle.reset_new_accounts()

    c = TestClient(app)
    r = c.post("/api/auth/signup",
               json={"handle": handle, "passphrase": "a long enough passphrase"})
    assert r.status_code == 201, r.text
    return c


# ---------------------------------------------------------------- isolation

def test_the_emergency_fallback_never_depends_on_our_data() -> None:
    """The one safety line that cannot go stale, because it is not a number we store.

    She knows her own emergency number better than this app does. Verifying six
    countries found two dead government pages and an organisation contradicting itself
    about its own number — against that, the fallback has to be something no file of
    ours can get wrong.
    """
    from backend.api.account import EMERGENCY_NOTE

    check("it points at her own local number",
          "local emergency number" in EMERGENCY_NOTE)
    for digits in ("911", "999", "112", "000", "119"):
        check(f"it does not hard-code {digits}", digits not in EMERGENCY_NOTE)

    c = new_client("fallback-check")
    # Present even for a country the directory knows nothing about.
    body = c.get("/api/resources", params={"region": "KE"}).json()
    check("carried even when nothing is curated",
          body["emergency_note"] == EMERGENCY_NOTE)
    check("and the staleness note only appears beside actual entries",
          body["staleness_note"] is None)


def test_location_is_never_inferred_from_the_request() -> None:
    """The privacy line on international resources.

    Christine asked whether this needs location-based servicing. It does not, and for
    this app it must not: a user may be on a monitored device, an IP-derived country is
    wrong often enough (VPN, travel, a foreign SIM) that acting on it in a crisis is
    worse than admitting we do not know, and a location quietly derived is a location
    quietly stored.
    """
    c = new_client("geo-check")

    # Headers that a naive implementation would read. None may change the answer.
    plain = c.get("/api/resources").json()
    spoofed = c.get("/api/resources", headers={
        "X-Forwarded-For": "203.0.113.7",
        "CF-IPCountry": "JP",
        "X-Real-IP": "203.0.113.7",
        "Accept-Language": "ja-JP,ja;q=0.9",
    }).json()
    check("location headers change nothing", plain == spoofed)
    check("and the region is reported as unset", plain["region_source"] == "unset")
    check("an empty directory says so honestly rather than serving US numbers",
          plain["resources"] == [] or plain["note"] is None)

    # The source must not reach for the client address either. Checked by MECHANISM,
    # not by header name: the route's own docstring names the headers it refuses to
    # read, and a test that matched those words would fail on the explanation of the
    # rule rather than on a breach of it.
    import ast

    for path in sorted((PROJECT_DIR / "backend" / "api").glob("*.py")):
        tree = ast.parse(path.read_text())
        code = {
            f"{getattr(n.value, 'id', '')}.{n.attr}"
            for n in ast.walk(tree) if isinstance(n, ast.Attribute)
        }
        imported = {
            alias.name for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom) for alias in n.names
        }
        # `request.cookies` is legitimate and necessary — it is how a route learns whose
        # data it is looking at. Everything else on the request object is connection
        # metadata, which is what this rule is about.
        reached = {c.split(".", 1)[1] for c in code if c.startswith("request.")}
        check(f"{path.name} touches only the session cookie on the request",
              reached <= {"cookies"},
              f"also reaches: {sorted(reached - {'cookies'})}")
        assert imported is not None  # (kept: Request may be imported for the cookie)

    # She sets it herself, and can take it back.
    c.patch("/api/auth/preferences", json={"region": "jp"})
    after = c.get("/api/resources").json()
    check("her own setting is used", after["region"] == "JP")
    check("and is reported as hers", after["region_source"] == "account")
    bad = c.patch("/api/auth/preferences", json={"region": "somewhere in Kenya"})
    check("free-text location is refused", bad.status_code == 422, bad.text)
    c.patch("/api/auth/preferences", json={"region": ""})
    check("clearing works", c.get("/api/resources").json()["region_source"] == "unset")


def test_relevance_is_per_profile_and_changeable() -> None:
    """Christine, 2026-11-12: Compatible Relationship Intentions *could* matter for a
    one-night stand — somebody may not want one with a person who wants a relationship.

    Which is the point: whether a standard applies here is the user's call, not a
    property of the encounter type. And changing it must never reach another profile.
    """
    c = new_client("relevance-user")
    a = c.post("/api/profiles", json={"name": "One Night Stand KRYteria"}).json()
    b = c.post("/api/profiles", json={"name": "Husband KRYteria"}).json()
    crit = c.post("/api/criteria", json={
        "value": "Compatible relationship intentions",
        "desired_behavior": "Wants the same kind of thing I do"}).json()

    c.post(f"/api/profiles/{a['id']}/criteria",
           json={"criterion_id": crit["id"], "relevance": "not_applicable"})
    c.post(f"/api/profiles/{b['id']}/criteria",
           json={"criterion_id": crit["id"], "tier": "mandatory"})

    r = c.patch(f"/api/profiles/{a['id']}/criteria/{crit['id']}",
                json={"relevance": "relevant", "tier": "mandatory"})
    check("relevance can be changed", r.status_code == 200, r.text)

    on_a = c.get(f"/api/profiles/{a['id']}/criteria").json()[0]
    on_b = c.get(f"/api/profiles/{b['id']}/criteria").json()[0]
    check("it took effect here", on_a["relevance"] == "relevant")
    check("and the tier came with it", on_a["tier"] == "mandatory")
    check("the other profile is untouched", on_b["relevance"] == "relevant")

    back = c.patch(f"/api/profiles/{a['id']}/criteria/{crit['id']}",
                   json={"relevance": "not_applicable"})
    check("and it can be set back", back.status_code == 200)
    check("not applicable again",
          c.get(f"/api/profiles/{a['id']}/criteria").json()[0]["relevance"]
          == "not_applicable")

    empty = c.patch(f"/api/profiles/{a['id']}/criteria/{crit['id']}", json={})
    check("an empty change is refused", empty.status_code == 422)


def test_a_quick_log_can_be_read_afterwards() -> None:
    """Choosing the fast path once must not lock somebody out of the considered one."""
    c = new_client("analyse-later")
    p = c.post("/api/people", json={"alias": "Alex"}).json()
    prof = c.post("/api/profiles", json={"name": "Dating KRYteria"}).json()
    entry = c.post("/api/entries/structured", json={
        "what_happened": "Plans changed at short notice. They followed through later.",
        "how_it_affected": "It landed: mixed",
        "person_id": p["id"], "profile_id": prof["id"]}).json()

    r = c.post(f"/api/entries/{entry['id']}/analyse",
               json={"profile_id": prof["id"], "person_id": p["id"]})
    check("a saved entry can be analysed later", r.status_code == 200, r.text)
    body = r.json()
    check("and it produced an analysis", body["analysis"] is not None)
    check("without creating a second entry", body["entry"]["id"] == entry["id"])

    missing = c.post("/api/entries/999999/analyse", json={})
    check("another account's entry is 404, never 403", missing.status_code == 404)


def test_profiles_can_be_renamed_and_put_away_but_never_deleted() -> None:
    """Christine, 2026-11-12: *"users may want to adjust their profiles, or even delete
    them! as their dating lives change"* — then, on seeing what delete would take:
    *"oh maybe it should just be an archive then. no deletion."*

    Right, and it matches the rest: criteria are versioned rather than overwritten, and
    assessment history keeps every transition. A profile holds what somebody thought at
    the time. Archiving hides it; the genuine need to erase lives at account level.
    """
    c = new_client("profile-editor")
    p = c.post("/api/profiles", json={
        "name": "Fuck Buddy KRYteria", "objective": "Ongoing casual",
        "context_label": "Ongoing casual"}).json()
    crit = c.post("/api/criteria", json={
        "value": "Discretion", "desired_behavior": "Keeps it between us"}).json()
    c.post(f"/api/profiles/{p['id']}/criteria",
           json={"criterion_id": crit["id"], "tier": "mandatory"})

    r = c.patch(f"/api/profiles/{p['id']}", json={"name": "Casual KRYteria"})
    check("a profile can be renamed", r.status_code == 200, r.text)
    check("the new name sticks", r.json()["name"] == "Casual KRYteria")
    check("and the configuration survived the rename",
          len(c.get(f"/api/profiles/{p['id']}/criteria").json()) == 1)

    other = c.post("/api/profiles", json={"name": "Husband KRYteria"}).json()
    clash = c.patch(f"/api/profiles/{other['id']}", json={"name": "Casual KRYteria"})
    check("a duplicate name is refused", clash.status_code == 409, clash.text)

    arch = c.post(f"/api/profiles/{p['id']}/archive?archived=true")
    check("a profile can be put away", arch.status_code == 200, arch.text)
    names = [x["name"] for x in c.get("/api/profiles").json()]
    check("and disappears from the normal list", "Casual KRYteria" not in names)
    all_names = [x["name"] for x in
                 c.get("/api/profiles", params={"include_archived": True}).json()]
    check("but is still there when asked for", "Casual KRYteria" in all_names)
    check("with everything under it intact",
          len(c.get(f"/api/profiles/{p['id']}/criteria").json()) == 1)

    back = c.post(f"/api/profiles/{p['id']}/archive?archived=false")
    check("and it comes back", back.status_code == 200)
    check("into the normal list",
          "Casual KRYteria" in [x["name"] for x in c.get("/api/profiles").json()])

    # The structural promise: there is no route that destroys one.
    gone = c.delete(f"/api/profiles/{p['id']}")
    check("there is no per-profile delete route", gone.status_code in (404, 405),
          f"got {gone.status_code} — a destructive route was added")


def test_data_isolation() -> None:
    """Two accounts. One must not be able to see or touch the other's anything."""
    alice = new_client("alice")
    bob = new_client("bob")

    crit = alice.post("/api/criteria", json={
        "value": "Follow-through", "desired_behavior": "Does what they said"}).json()
    prof = alice.post("/api/profiles", json={"name": "Boyfriend KRYteria"}).json()
    person = alice.post("/api/people", json={"alias": "J"}).json()
    entry = alice.post("/api/brain-dump", json={
        "text": "He was late again.", "analyze": False}).json()["entry"]
    alice.post(f"/api/profiles/{prof['id']}/criteria",
               json={"criterion_id": crit["id"], "tier": "mandatory"})

    # Bob sees none of it.
    check("bob's criteria list is empty", bob.get("/api/criteria").json() == [])
    check("bob's profile list is empty", bob.get("/api/profiles").json() == [])
    check("bob's entries list is empty", bob.get("/api/entries").json() == [])
    check("bob's people list is empty", bob.get("/api/people").json() == [])

    # Bob cannot reach them by id either — and gets 404, not 403, so the response does
    # not confirm that the row exists.
    for label, resp in [
        ("criterion history", bob.get(f"/api/criteria/{crit['id']}/history")),
        ("profile criteria", bob.get(f"/api/profiles/{prof['id']}/criteria")),
        ("entry", bob.get(f"/api/entries/{entry['id']}")),
        ("checklist", bob.get(f"/api/criteria/{crit['id']}/checklist")),
    ]:
        check(f"bob gets 404 for alice's {label}", resp.status_code == 404,
              f"got {resp.status_code}")

    # And cannot write to them.
    r = bob.post(f"/api/profiles/{prof['id']}/criteria",
                 json={"criterion_id": crit["id"]})
    check("bob cannot add to alice's profile", r.status_code == 404, f"got {r.status_code}")
    r = bob.post(f"/api/criteria/{crit['id']}/revise", json={"value": "hacked"})
    check("bob cannot revise alice's criterion", r.status_code == 404,
          f"got {r.status_code}")
    r = bob.put("/api/assessments", json={
        "profile_id": prof["id"], "criterion_id": crit["id"],
        "person_id": person["id"], "status": "pass"})
    check("bob cannot assess on alice's profile", r.status_code == 404,
          f"got {r.status_code}")
    r = bob.delete(f"/api/entries/{entry['id']}")
    check("bob cannot delete alice's entry", r.status_code == 404, f"got {r.status_code}")

    # The one cross-account WRITE this test did not cover, which is exactly where the
    # hole was: `record_checklist_observation` stamped account_id without checking it,
    # and when the check was added the new NotOwned took an old exit that returned 422.
    # A 404 here is the contract; anything else is a bug even when nothing leaks.
    for probe in (1, 2, 3):
        r = bob.post(f"/api/checklist/{probe}/observe", json={"state": "observed"})
        check(f"bob gets 404 observing against item {probe}", r.status_code == 404,
              f"got {r.status_code}")

    # The bulk paths are new doors into the same rows, so they get the same probe.
    r = bob.post(f"/api/profiles/{prof['id']}/criteria/bulk", json={})
    check("bob cannot add-all into alice's profile", r.status_code == 404,
          f"got {r.status_code}")
    bobs_profile = bob.post("/api/profiles", json={"name": "Mine"}).json()
    r = bob.post(f"/api/profiles/{bobs_profile['id']}/criteria/bulk",
                 json={"criterion_ids": [crit["id"]]})
    check("bob cannot pull alice's criterion into his own profile",
          r.status_code == 404, f"got {r.status_code}")
    check("and his profile stayed empty",
          bob.get(f"/api/profiles/{bobs_profile['id']}/criteria").json() == [])

    # Alice's data is untouched.
    check("alice still has her criterion", len(alice.get("/api/criteria").json()) == 1)
    check("alice's criterion is unchanged",
          alice.get("/api/criteria").json()[0]["value"] == "Follow-through")


def test_anonymous_requests_are_refused() -> None:
    anon = TestClient(app)
    for path in ("/api/criteria", "/api/profiles", "/api/entries", "/api/progress",
                 "/api/export", "/api/auth/me", "/api/usage"):
        check(f"{path} requires a session", anon.get(path).status_code == 401)
    check("brain dump requires a session",
          anon.post("/api/brain-dump", json={"text": "x"}).status_code == 401)
    # A forged cookie is rejected by the signature, not merely unparsed.
    anon.cookies.set("kryteria_session", "eyJhY2NvdW50X2lkIjoxfQ.forged")
    check("a forged session cookie is rejected",
          anon.get("/api/auth/me").status_code == 401)


def test_auth_basics() -> None:
    c = TestClient(app)
    r = c.post("/api/auth/signup", json={"handle": "shorty", "passphrase": "short"})
    check("a short passphrase is refused", r.status_code == 422, f"got {r.status_code}")

    r = c.post("/api/auth/signup",
               json={"handle": "dup", "passphrase": "a long enough passphrase"})
    check("signup works", r.status_code == 201)
    check("no hash is ever returned", "passphrase_hash" not in r.json())
    check("the default tone is clarity", r.json()["tone_mode"] == "clarity")

    c2 = TestClient(app)
    r = c2.post("/api/auth/signup",
                json={"handle": "dup", "passphrase": "another long passphrase"})
    check("a duplicate handle is refused", r.status_code == 409, f"got {r.status_code}")

    r = c2.post("/api/auth/signin", json={"handle": "dup", "passphrase": "wrong one here"})
    check("a wrong passphrase is refused", r.status_code == 401)
    check("the error does not say whether the handle exists",
          "handle or passphrase" in r.json()["detail"].lower())

    r = c2.post("/api/auth/signin",
                json={"handle": "nobody-here", "passphrase": "a long enough passphrase"})
    check("an unknown handle gives the same message", r.status_code == 401)


# ---------------------------------------------------------------- profiles

def test_profile_independence_over_http() -> None:
    c = new_client("profiles-user")
    attraction = c.post("/api/criteria", json={
        "value": "Physical attraction", "desired_behavior": "I want to kiss him"}).json()
    kids = c.post("/api/criteria", json={
        "value": "Wants children", "desired_behavior": "Wants kids soon"}).json()

    husband = c.post("/api/profiles", json={"name": "Husband KRYteria"}).json()
    ons = c.post("/api/profiles", json={"name": "One Night Stand KRYteria"}).json()

    c.post(f"/api/profiles/{husband['id']}/criteria",
           json={"criterion_id": attraction["id"], "tier": "preferred"})
    c.post(f"/api/profiles/{husband['id']}/criteria",
           json={"criterion_id": kids["id"], "tier": "mandatory"})
    c.post(f"/api/profiles/{ons['id']}/criteria",
           json={"criterion_id": attraction["id"], "tier": "mandatory"})
    c.post(f"/api/profiles/{ons['id']}/criteria",
           json={"criterion_id": kids["id"], "relevance": "not_applicable"})

    def tier(profile_id, criterion_id):
        rows = c.get(f"/api/profiles/{profile_id}/criteria").json()
        return next(r["tier"] for r in rows if r["criterion_id"] == criterion_id)

    check("attraction is Preferred for a husband",
          tier(husband["id"], attraction["id"]) == "preferred")
    check("and Mandatory for a one-night stand",
          tier(ons["id"], attraction["id"]) == "mandatory")
    check("one criterion, one library row", len(c.get("/api/criteria").json()) == 2)

    r = c.patch(f"/api/profiles/{husband['id']}/criteria/{attraction['id']}",
                json={"tier": "mandatory"})
    check("the tier change applies", r.status_code == 200)
    check("the other profile is untouched",
          tier(ons["id"], attraction["id"]) == "mandatory")
    c.patch(f"/api/profiles/{ons['id']}/criteria/{attraction['id']}",
            json={"tier": "aspirational"})
    check("and it works the other way",
          tier(husband["id"], attraction["id"]) == "mandatory")

    # Copying is explicit and produces an independent configuration.
    casual = c.post("/api/profiles", json={"name": "Fuck Buddy KRYteria"}).json()
    r = c.post(f"/api/profiles/{casual['id']}/copy-criteria",
               json={"source_profile_id": husband["id"]})
    check("copying brings the criteria across", r.json()["copied"] == 2)
    c.patch(f"/api/profiles/{casual['id']}/criteria/{attraction['id']}",
            json={"tier": "preferred"})
    check("editing the copy does not touch the source",
          tier(husband["id"], attraction["id"]) == "mandatory")

    r = c.post("/api/profiles", json={"name": "Husband KRYteria"})
    check("a duplicate profile name is refused", r.status_code == 409)


def test_not_applicable_over_http() -> None:
    c = new_client("na-user")
    kids = c.post("/api/criteria", json={
        "value": "Wants children", "desired_behavior": "Wants kids"}).json()
    ons = c.post("/api/profiles", json={"name": "One Night Stand KRYteria"}).json()
    husband = c.post("/api/profiles", json={"name": "Husband KRYteria"}).json()
    c.post(f"/api/profiles/{ons['id']}/criteria",
           json={"criterion_id": kids["id"], "relevance": "not_applicable"})
    c.post(f"/api/profiles/{husband['id']}/criteria",
           json={"criterion_id": kids["id"], "tier": "mandatory"})
    person = c.post("/api/people", json={"alias": "J"}).json()

    ons_board = c.get("/api/assessments",
                      params={"profile_id": ons["id"], "person_id": person["id"]}).json()
    husband_board = c.get("/api/assessments",
                          params={"profile_id": husband["id"],
                                  "person_id": person["id"]}).json()
    check("not relevant reads not_applicable",
          ons_board[0]["assessment"] == "not_applicable")
    check("unassessed elsewhere reads unknown",
          husband_board[0]["assessment"] == "unknown")
    check("not_applicable is not fail", ons_board[0]["assessment"] != "fail")
    check("the criterion survives in the library",
          len(c.get("/api/criteria").json()) == 1)


# ---------------------------------------------------------------- assessments

def test_only_the_user_sets_a_status() -> None:
    c = new_client("status-user")
    crit = c.post("/api/criteria", json={
        "value": "Consistency", "desired_behavior": "Follows through"}).json()
    prof = c.post("/api/profiles", json={"name": "Boyfriend KRYteria"}).json()
    c.post(f"/api/profiles/{prof['id']}/criteria",
           json={"criterion_id": crit["id"], "tier": "mandatory"})
    person = c.post("/api/people", json={"alias": "J"}).json()

    r = c.put("/api/assessments", json={
        "profile_id": prof["id"], "criterion_id": crit["id"],
        "person_id": person["id"], "status": "pass"})
    check("the user can set a status", r.status_code == 200)
    check("the transition is recorded", len(r.json()["history"]) == 1)
    check("it records what it came from",
          r.json()["history"][0]["previous_status"] == "unknown")
    check("and that the user did it", r.json()["history"][0]["origin"] == "user")

    r = c.put("/api/assessments", json={
        "profile_id": prof["id"], "criterion_id": crit["id"],
        "person_id": person["id"], "status": "sort-of"})
    check("an invalid status is refused", r.status_code == 422)

    # Editing a proposal requires naming the status the user chose.
    r = c.post("/api/proposals/999/decide", json={"resolution": "edited"})
    check("editing with no chosen status is refused", r.status_code == 422)
    r = c.post("/api/proposals/999/decide", json={"resolution": "accepted"})
    check("a proposal that does not exist is a 404", r.status_code == 404)


def test_decisions_and_the_postponement_probe() -> None:
    c = new_client("decisions-user")
    crit = c.post("/api/criteria", json={
        "value": "Follow-through", "desired_behavior": "Does what they said"}).json()

    for i in range(2):
        r = c.post("/api/decisions", json={
            "choice": "more_time", "criterion_id": crit["id"]})
        check(f"postponement {i + 1} is recorded", r.status_code == 201)
        check("the probe is not due yet", r.json()["probe_available"] is False)

    r = c.post("/api/decisions", json={"choice": "more_time", "criterion_id": crit["id"]})
    check("at the third, the probe becomes available",
          r.json()["probe_available"] is True)
    check("the count is exact", r.json()["postponements_on_this_concern"] == 3)

    r = c.post("/api/decisions", json={"choice": "undecided", "criterion_id": crit["id"]})
    check("undecided is a legitimate recorded decision", r.status_code == 201)
    check("and is not counted as a postponement",
          r.json()["postponements_on_this_concern"] == 3)

    r = c.post("/api/decisions", json={"choice": "dump_him"})
    check("an invented decision is refused", r.status_code == 422)


# ---------------------------------------------------------------- journal

def test_brain_dump_saves_before_it_analyses() -> None:
    c = new_client("dump-user")
    r = c.post("/api/brain-dump", json={"text": "We had dinner. He was funny.",
                                        "analyze": False})
    check("an unanalysed entry is saved", r.status_code == 201)
    check("the entry comes back", r.json()["entry"]["body"].startswith("We had dinner"))
    check("and no analysis was run", r.json()["analysis"] is None)
    check("no domain had to exist first", r.json()["entry"]["domain_id"] is not None)

    r = c.post("/api/brain-dump", json={"text": "   "})
    check("an empty entry is refused", r.status_code == 422)

    entries = c.get("/api/entries").json()
    check("the entry is listed", len(entries) == 1)
    found = c.get("/api/entries", params={"search": "dinner"}).json()
    check("search finds it", len(found) == 1)


def test_checklist_tick_does_not_set_pass() -> None:
    c = new_client("checklist-user")
    crit = c.post("/api/criteria", json={
        "value": "Emotional maturity", "desired_behavior": "Handles disagreement"}).json()
    prof = c.post("/api/profiles", json={"name": "Boyfriend KRYteria"}).json()
    c.post(f"/api/profiles/{prof['id']}/criteria",
           json={"criterion_id": crit["id"], "tier": "mandatory"})
    person = c.post("/api/people", json={"alias": "J"}).json()

    from backend.api.deps import get_store
    store = get_store()
    account_id = store.verify_account("checklist-user", "a long enough passphrase")
    items = store.save_checklist_items(account_id, crit["id"], [
        {"text": f"Indicator {i}", "source_level": "agent_hypothesis"} for i in range(4)
    ], profile_id=prof["id"])

    for item in items:
        r = c.post(f"/api/checklist/{item}/observe", json={"person_id": person["id"]})
        check("the observation is recorded", r.status_code == 201)
    check("the response says it is only an observation",
          "does not change" in r.json()["note"])

    board = c.get("/api/assessments",
                  params={"profile_id": prof["id"], "person_id": person["id"]}).json()
    check("the criterion is still unknown after ticking every box",
          board[0]["assessment"] == "unknown")

    r = c.post(f"/api/checklist/{items[0]}/observe", json={"state": "nope"})
    check("an invalid observation state is refused", r.status_code == 422)


# ---------------------------------------------------------------- account

def test_retention_over_http() -> None:
    """The choice from the post-dump screen, and what it actually erases."""
    c = new_client("retention-user")

    # analyze=True runs the real workflow — demo mode needs no key and bills nothing.
    r = c.post("/api/brain-dump", json={
        "text": "A long private account of a difficult evening.",
        "retention": "keep_all"})
    kept = r.json()["entry"]["id"]
    check("keep_all leaves the narrative", r.json()["entry"]["body"] is not None)
    check("the response says what was kept",
          r.json()["retention"]["original_erased"] is False)

    r = c.post("/api/brain-dump", json={
        "text": "Another private account, written at 1am.",
        "retention": "analysis_only"})
    erased = r.json()["entry"]["id"]
    check("analysis_only erases the narrative in the same request",
          r.json()["entry"]["body"] is None)
    check("and says so", r.json()["retention"]["original_erased"] is True)

    check("the erased entry is still listed as a placeholder",
          any(e["id"] == erased for e in c.get("/api/entries").json()))
    check("but holds no text",
          c.get(f"/api/entries/{erased}").json()["body"] is None)

    # Changing the mind afterwards, from the screen that shows the analysis.
    r = c.post(f"/api/entries/{kept}/retention", json={"retention": "analysis_only"})
    check("retention can be changed after the fact", r.status_code == 200)
    check("the warning is explicit", "cannot be recovered" in r.json()["note"])
    check("the narrative is gone",
          c.get(f"/api/entries/{kept}").json()["body"] is None)

    report = c.get("/api/retention").json()
    check("the report counts erased originals", report["originals_erased"] == 2)
    check("and none still stored", report["originals_still_stored"] == 0)

    r = c.patch("/api/auth/preferences", json={"retention": "discard"})
    check("the default is settable", r.json()["retention"] == "discard")
    r = c.patch("/api/auth/preferences", json={"retention": "forever"})
    check("an invalid default is refused", r.status_code == 422)

    # A dump with no explicit choice follows the account default.
    r = c.post("/api/brain-dump", json={"text": "Follows the default."})
    check("the account default applies when none is given",
          r.json()["retention"]["retention"] == "discard")

    # Saving without analysis keeps what was written: there was no processing, so
    # analysis_only would erase the only thing the user created.
    c.patch("/api/auth/preferences", json={"retention": "analysis_only"})
    r = c.post("/api/brain-dump", json={"text": "Just a note.", "analyze": False})
    check("an unanalysed entry is kept as written",
          r.json()["entry"]["body"] == "Just a note.")
    check("and says why", "kept as written" in r.json()["note"])
    r = c.post("/api/brain-dump", json={
        "text": "Write it down and let it go.", "analyze": False, "retention": "discard"})
    check("but an explicit discard is still honoured",
          r.json()["entry"]["body"] is None)

    other = new_client("retention-other")
    r = other.post(f"/api/entries/{kept}/retention", json={"retention": "discard"})
    check("another account cannot erase your entry", r.status_code == 404,
          f"got {r.status_code}")


def test_no_route_accepts_another_users_identity() -> None:
    """There is no mechanism that could signal one user about another.

    Asserted against the OpenAPI schema rather than by reading the code, so a route added
    later with a user-identifying parameter fails this.
    """
    c = new_client("schema-user")
    spec = c.get("/openapi.json").json()

    offenders = []
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            for param in op.get("parameters", []):
                name = param["name"].lower()
                if name in {"account_id", "user_id", "handle", "email", "owner_id"}:
                    offenders.append(f"{method.upper()} {path} ?{param['name']}")
    check("no route takes another user's identifier as a parameter",
          not offenders, "; ".join(offenders))

    bodies = repr(spec.get("components", {}).get("schemas", {})).lower()
    for forbidden in ("share", "invite", "collaborat", "notify_person", "mention_user"):
        check(f"no schema mentions '{forbidden}'", forbidden not in bodies)


def test_quick_log_path_costs_nothing() -> None:
    """The structured alternative: a person, a structured entry, and the user's own
    mappings — none of which needs a model call."""
    c = new_client("quicklog-user")

    person = c.post("/api/people", json={"alias": "R.", "role_label": "running club"}).json()
    check("a person can be added", person["alias"] == "R.")
    check("only the alias is stored", person["role_label"] == "running club")
    check("no real-name field exists", "name" not in person and "email" not in person)

    crit = c.post("/api/criteria", json={
        "value": "Follow-through", "desired_behavior": "Does what they said"}).json()
    prof = c.post("/api/profiles", json={"name": "Boyfriend KRYteria"}).json()
    c.post(f"/api/profiles/{prof['id']}/criteria",
           json={"criterion_id": crit["id"], "tier": "mandatory"})

    entry = c.post("/api/entries/structured", json={
        "what_happened": "Plans changed at short notice",
        "how_it_affected": "It landed: mixed",
        "profile_id": prof["id"], "person_id": person["id"]}).json()
    check("a structured entry is saved", entry["entry_mode"] == "structured")
    check("and keeps what was tapped",
          entry["what_happened"] == "Plans changed at short notice")

    r = c.post("/api/evidence-links", json={
        "entry_id": entry["id"], "criterion_id": crit["id"],
        "relation": "contradicting", "profile_id": prof["id"],
        "person_id": person["id"]})
    check("the user can map their own evidence", r.status_code == 201)

    links = c.get("/api/evidence-links").json()
    mine = [l for l in links if l["proposed_by"] == "user"]
    check("the link is recorded", len(mine) == 1)
    check("a user's own mapping needs no confirmation",
          mine[0]["resolution"] == "accepted")
    check("and is marked as the user's, not research or a guess",
          mine[0]["source_level"] == "user_stated")

    # The entry must actually be attached to the person, or "what recurs with them"
    # has nothing to work from. This was broken: person_id was accepted and ignored.
    full = c.get(f"/api/entries/{entry['id']}").json()
    check("the entry is linked to the person", full["people"] == ["R."])

    usage = c.get("/api/usage").json()
    check("none of that spent a model call", usage["today"]["calls"] == 0)

    other = new_client("quicklog-other")
    r = other.post("/api/evidence-links", json={
        "entry_id": entry["id"], "criterion_id": crit["id"], "relation": "supporting"})
    check("another account cannot map against your entry", r.status_code == 404,
          f"got {r.status_code}")


def test_removing_a_person() -> None:
    """Two different acts: taking a name off the list, and erasing they were here."""
    c = new_client("remove-user")
    crit = c.post("/api/criteria", json={"value": "X", "desired_behavior": "Y"}).json()
    prof = c.post("/api/profiles", json={"name": "P"}).json()
    c.post(f"/api/profiles/{prof['id']}/criteria", json={"criterion_id": crit["id"]})

    # Keeping the entries, which is the default.
    a = c.post("/api/people", json={"alias": "A"}).json()
    c.post("/api/entries/structured",
           json={"what_happened": "about A", "person_id": a["id"]})
    c.put("/api/assessments", json={"profile_id": prof["id"], "criterion_id": crit["id"],
                                    "person_id": a["id"], "status": "pass"})

    fp = c.get(f"/api/people/{a['id']}/footprint").json()
    check("the footprint is shown before deleting", fp["entries"] == 1)
    check("and counts the assessments that would go", fp["assessments"] == 1)

    before = len(c.get("/api/entries").json())
    r = c.delete(f"/api/people/{a['id']}?delete_entries=false").json()
    check("removing keeps the journal", len(c.get("/api/entries").json()) == before)
    check("but takes the assessments", r["assessments_removed"] == 1)
    check("and says which it did", "still in your journal" in r["note"])
    check("the person is gone", all(p["id"] != a["id"] for p in c.get("/api/people").json()))

    # Erasing everything about them.
    b = c.post("/api/people", json={"alias": "B"}).json()
    c.post("/api/entries/structured",
           json={"what_happened": "about B", "person_id": b["id"]})
    mid = len(c.get("/api/entries").json())
    r = c.delete(f"/api/people/{b['id']}?delete_entries=true").json()
    check("deleting entries too actually removes them", r["entries_removed"] == 1,
          f"got {r['entries_removed']}")
    check("and the journal is shorter", len(c.get("/api/entries").json()) == mid - 1)
    check("and it says so", "everything you'd written" in r["note"])

    other = new_client("remove-other")
    person = c.post("/api/people", json={"alias": "C"}).json()
    check("another account cannot see the footprint",
          other.get(f"/api/people/{person['id']}/footprint").status_code == 404)
    check("nor remove them",
          other.delete(f"/api/people/{person['id']}").status_code == 404)


def test_export_and_delete() -> None:
    c = new_client("export-user")
    c.post("/api/criteria", json={"value": "X", "desired_behavior": "Y"})
    c.post("/api/brain-dump", json={"text": "something private", "analyze": False})

    blob = c.get("/api/export").json()
    check("export carries the account", blob["account"]["handle"] == "export-user")
    check("export omits the hash", "passphrase_hash" not in blob["account"])
    check("export carries entries", len(blob["entries"]) == 1)
    check("no argon2 material anywhere in the export", "$argon2" not in repr(blob))

    r = c.post("/api/account/delete", json={"passphrase": "wrong",
                                            "confirm": "DELETE EVERYTHING"})
    check("deletion needs the right passphrase", r.status_code == 403)
    r = c.post("/api/account/delete", json={"passphrase": "a long enough passphrase",
                                            "confirm": "oops"})
    check("deletion needs the typed confirmation", r.status_code == 422)

    r = c.post("/api/account/delete", json={"passphrase": "a long enough passphrase",
                                            "confirm": "DELETE EVERYTHING"})
    check("deletion succeeds with both", r.status_code == 200)
    check("the session is cleared", c.get("/api/auth/me").status_code == 401)


def test_usage_reports_unavailable_rather_than_zero() -> None:
    c = new_client("usage-user")
    r = c.get("/api/usage").json()
    check("usage reports the mode", r["mode"] == "demo")
    check("demo usage is flagged simulated", r["simulated"] is True)
    check("it says plainly that nothing is billed", "nothing here is billed" in (r["note"] or ""))

    proj = c.get("/api/usage/projection").json()
    check("a projection with no billable runs is refused",
          proj["available"] is False)
    check("and says why", "excluded from cost figures" in proj["reason"])


def test_resources_are_always_readable() -> None:
    """Declining an offer stops the app volunteering. It never stops the user asking."""
    c = new_client("resources-user")
    from backend.api.deps import get_store

    store = get_store()
    if not store.list_resources(region="US"):
        import json
        blob = json.loads((PROJECT_DIR / "data" / "resources_us.json").read_text())
        store.seed_resources(blob["resources"])

    # The route answers with the region it used as well as the rows, so a caller can
    # tell "nothing curated for your country" from "nothing matched your category".
    body = c.get("/api/resources", params={"region": "US"}).json()
    r = body["resources"]
    check("resources are readable on request", len(r) > 0)
    check("every one carries a verification date", all(x["verified_at"] for x in r))
    check("emergency is distinguished from confidential support",
          {x["kind"] for x in r} >= {"emergency", "confidential_support"})
    check("the region used is reported back", body["region"] == "US")
    check("and where it came from", body["region_source"] == "query")

    empty = c.get("/api/resources", params={"region": "KE"}).json()
    check("a country with nothing curated returns no rows", empty["resources"] == [])
    check("and says so rather than substituting another country's numbers",
          "will not invent one" in (empty["note"] or ""), str(empty["note"]))

    account_id = store.verify_account("resources-user", "a long enough passphrase")
    offer = store.record_resource_offer(account_id, [1], "disclosure")
    resp = c.post(f"/api/resource-offers/{offer}/respond", json={"response": "declined"})
    check("a decline is accepted", resp.status_code == 200)
    check("and acknowledged in words", "won't bring those up again" in resp.json()["note"])
    check("declining does not stop them being readable",
          len(c.get("/api/resources").json()) > 0)
    check("immediate danger still surfaces after a decline",
          store.should_offer_resources(account_id, "immediate_danger") is True)
    check("but a disclosure no longer volunteers them",
          store.should_offer_resources(account_id, "disclosure") is False)


# ---------------------------------------------------------------- health + demo

def test_health_is_diagnosable() -> None:
    c = TestClient(app)
    r = c.get("/api/health")
    check("health needs no session", r.status_code == 200)
    body = r.json()
    check("it reports the mode", body["mode"] == "demo")
    check("it says the model", body["model"] == "kryteria-demo")
    check("it says where it looked for a key", "env_source" in body)
    check("it says whether prices are loaded", body["prices_loaded"] is False)
    check("it says whether the front end is built", "frontend_built" in body)
    check("it explains demo mode", "demo mode" in (body["note"] or "").lower())
    check("no key material is in the response", "PORTKEY" not in repr(body).upper()
          or "api_key_found" in body)


def test_an_unknown_api_path_is_a_404_and_not_the_single_page_app() -> None:
    """A mistyped endpoint must fail like an endpoint, not answer like a page.

    The SPA is mounted on a catch-all so the client router can own its own paths. That
    caught ``/api/...`` too, so every unmatched endpoint returned 200 and a page of HTML:
    a client got a JSON parse error rather than a 404, and asking a deployment whether it
    had a route answered "yes" no matter what. That is how a redeploy that never happened
    looked, for a while, like one that had.
    """
    anon = TestClient(app)
    missing = anon.get("/api/no-such-endpoint-exists")
    check("an unknown /api path 404s", missing.status_code == 404,
          f"got {missing.status_code}")
    check("and answers as JSON, not a page",
          missing.headers.get("content-type", "").startswith("application/json"),
          missing.headers.get("content-type", ""))

    page = anon.get("/checklist")
    check("a client-side route still serves the app", page.status_code == 200)
    check("and that one is HTML",
          page.headers.get("content-type", "").startswith("text/html"))


def test_someone_who_has_not_said_where_they_are_is_still_offered_something() -> None:
    """A region-less account must not be offered nothing at a serious concern level.

    This was live, and no single piece of it was a bug. An account that has not said
    where it is sees GLOBAL rows only — right, because a US number offered to somebody in
    Osaka is the same failure as an invented one. ``resources_to_offer`` withholds
    emergency numbers below ``immediate_danger`` — right, because volunteering 911 for a
    pattern-level concern overstates what was described. And the only GLOBAL row was an
    emergency number.

    Three correct behaviours composing into a wrong outcome: disclose physical harm with
    no region set, and KRYteria offered nothing at all. The fix was a global entry that
    is not an emergency service — a directory, which is the only honest thing to hand
    somebody whose country you do not know.

    The emergency number must still be withheld below immediate danger. Fixing the first
    problem by loosening that would trade one wrong answer for another.
    """
    import tempfile as _tf
    from pathlib import Path as _P

    from backend.agents import safety as _safety
    from backend.models import SafetyOutput as _SafetyOutput
    from backend.seed_characters import load_shared_reference_data
    from backend.store import Store as _Store

    store = _Store(_P(_tf.mkdtemp()) / "noregion.db")
    load_shared_reference_data(store)
    account_id = store.create_account("no-region-user", "a long enough passphrase")
    check("the account really has no region",
          (store.get_account(account_id) or {}).get("region") is None)

    for level in ("potential", "pattern", "disclosure"):
        offered = _safety.resources_to_offer(store, account_id, _SafetyOutput(
            concern_detected=True, category="physical", concern_level=level,
            suggested_action="offer_resources", acknowledgement="x", rationale="y"))
        check(f"something is offered at {level}", bool(offered),
              "a region-less account was offered nothing")
        check(f"and no emergency number is volunteered at {level}",
              all(r["kind"] != "emergency" for r in offered),
              str([r["name"] for r in offered]))

    urgent = _safety.resources_to_offer(store, account_id, _SafetyOutput(
        concern_detected=True, category="physical", concern_level="immediate_danger",
        suggested_action="halt_and_route", acknowledgement="x", rationale="y"))
    check("an emergency number IS surfaced at immediate danger",
          any(r["kind"] == "emergency" for r in urgent),
          str([r["name"] for r in urgent]))


def test_a_fresh_deployment_has_resources_and_research() -> None:
    """The two things whose absence fails silently.

    Both were loaded by seed_demo, and retiring it took them with it. Nothing broke
    loudly, because the correct behaviour when they are missing is quiet:

      * With no resources, the safety layer can recognise a concern perfectly and then
        have nothing to offer — and refusing to invent a hotline is right, so the empty
        result looks like the product working. It was live on the hosted app in exactly
        that state.
      * With no research notes, ``citable_refs()`` is empty, so every ``research_ref``
        fails to resolve and the write is refused. That is also correct behaviour, and
        it disables the entire research layer without a single error.

    Correct-when-missing is precisely why these need a test rather than a convention.
    """
    import tempfile as _tf
    from pathlib import Path as _P

    from backend.seed_characters import seed
    from backend.store import Store as _Store

    fresh = _Store(_P(_tf.mkdtemp()) / "deployment.db")
    seed(fresh, reset=True)

    us = fresh.list_resources(region="US", include_global=False)
    check("a fresh deployment has US support resources", len(us) >= 3, f"{len(us)}")
    check("and resources for somewhere outside the US",
          bool(fresh.list_resources(region="GB", include_global=False)))
    check("and a GLOBAL fallback for an unset region",
          bool(fresh.list_resources(region=None)))

    # The US file loads after the international one alphabetically. list_resources folds
    # GLOBAL into every region by default, so a guard written without
    # include_global=False sees the GLOBAL row and skips US entirely.
    check("the GLOBAL row does not mask a country's own resources",
          len(us) >= 3,
          "US resources were skipped because a GLOBAL row already existed")

    citable = fresh.citable_refs()
    check("research notes are loaded and citable", len(citable) >= 10, f"{len(citable)}")

    # Verification has to survive a rebuild, because the database is thrown away on every
    # deploy — it lives in the committed pack, not only in the row. And nothing may become
    # citable without it: a ref that resolves to an unverified row is the fabrication this
    # whole layer exists to make impossible.
    #
    # Note the two methods have different scopes on purpose: citable_refs queries the
    # table, while list_research_notes withholds safety_adjacent entries from agents. So
    # the counts differ legitimately, and comparing them proves nothing.
    import sqlite3 as _sq

    conn = _sq.connect(fresh.db_path)
    conn.row_factory = _sq.Row
    unverified_but_citable = [
        r["ref"] for r in conn.execute(
            "SELECT ref FROM research_notes WHERE verified_at IS NULL")
        if r["ref"] in citable
    ]
    check("no unverified note is citable", not unverified_but_citable,
          str(unverified_but_citable))
    total = conn.execute("SELECT COUNT(*) FROM research_notes").fetchone()[0]
    check("the pack arrives with its verification intact, not all pending",
          len(citable) >= total - 2, f"{len(citable)} citable of {total} loaded")


def test_security_headers_are_on_every_response() -> None:
    """Browser-enforced protections the server cannot apply itself.

    The app shipped without any of these. `frame-ancestors`/X-Frame-Options is the one
    that matters most here: framing is how somebody with access to a shared device could
    overlay or watch this interface, and the content is somebody's relationship journal.
    Referrer-Policy matters for the same reason at one remove — a URL here names the
    screen being read.
    """
    r = TestClient(app).get("/api/health")
    for header, expected in (
        ("X-Frame-Options", "DENY"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"),
        ("Cross-Origin-Opener-Policy", "same-origin"),
    ):
        check(f"{header} is set", r.headers.get(header) == expected,
              f"got {r.headers.get(header)!r}")

    csp = r.headers.get("Content-Security-Policy", "")
    check("a CSP is set", bool(csp))
    check("the app cannot be framed", "frame-ancestors 'none'" in csp, csp[:120])
    check("no script origin other than our own", "script-src 'self'" in csp, csp[:120])
    check("object-src is closed", "object-src 'none'" in csp, csp[:120])
    check("Permissions-Policy denies geolocation",
          "geolocation=()" in r.headers.get("Permissions-Policy", ""))


def test_signup_throttling_cannot_lock_somebody_out_of_their_own_account() -> None:
    """Rate-limiting sign-up must not become a denial-of-service against an owner.

    `throttle.py` keeps one counter per key. Charging failed sign-ups to the bare handle
    let anyone lock an existing account out of its OWN sign-in by posting sign-ups for
    that handle until the counter tripped — and a 409 means the handle exists, so the
    request being penalised is not a guess and the counter it fills belongs to somebody
    else. Sign-up is therefore throttled on a separate `signup:` key.
    """
    from backend import throttle
    throttle.reset()

    owner = new_client("victim")
    hostile = new_client("attacker")

    codes = [hostile.post("/api/auth/signup",
                          json={"handle": "victim", "passphrase": "x-long-enough-passphrase"}
                          ).status_code for _ in range(12)]
    check("sign-up itself is still rate-limited", 429 in codes, f"got {sorted(set(codes))}")

    r = owner.post("/api/auth/signin",
                   json={"handle": "victim", "passphrase": "a long enough passphrase"})
    check("the owner can still sign in", r.status_code == 200,
          f"got {r.status_code} — the attacker filled the owner's counter")


def test_credential_endpoints_are_throttled() -> None:
    """Guessing a passphrase against a known handle has to get slower.

    Handles are short and, for the demo accounts, published. Without this, sign-in could
    be called as fast as the network allowed.

    Two properties are asserted beyond "it refuses": a correct passphrase is also
    refused during cooldown (otherwise the throttle is trivially bypassed by interleaving
    guesses), and a success *clears* the counter, so somebody who mistyped their own
    passphrase a few times is not punished for the rest of the window.
    """
    from backend import throttle

    throttle.reset()
    handle = "throttled-user"
    first = TestClient(app).post(
        "/api/auth/signup", json={"handle": handle, "passphrase": "a long enough passphrase"})
    check("the account exists", first.status_code == 201, first.text[:120])
    throttle.reset()

    codes = [
        TestClient(app).post("/api/auth/signin",
                             json={"handle": handle, "passphrase": f"wrong-{i}"}).status_code
        for i in range(throttle.MAX_ATTEMPTS + 3)
    ]
    check("repeated guesses are eventually refused", 429 in codes, str(codes))
    check("but not on the first try", codes[0] == 401, str(codes[:2]))

    correct = TestClient(app).post(
        "/api/auth/signin", json={"handle": handle, "passphrase": "a long enough passphrase"})
    check("the right passphrase is also refused while in cooldown",
          correct.status_code == 429,
          "otherwise the throttle is bypassed by interleaving a real attempt")
    check("and it says how long to wait", correct.headers.get("Retry-After") is not None)

    # A success must clear the record, or a user who fumbles their own passphrase stays
    # locked out for the window even after getting it right.
    throttle.reset()
    ok = TestClient(app).post(
        "/api/auth/signin", json={"handle": handle, "passphrase": "a long enough passphrase"})
    check("a correct sign-in works once the window has cleared", ok.status_code == 200)
    throttle.record_failure(handle)
    throttle.record_success(handle)
    throttle.check(handle)          # raises if the success did not clear it
    check("a success clears the failure count", True)
    throttle.reset()


def test_a_session_cookie_does_not_last_forever() -> None:
    """The signed session has a server-side expiry, not just a cookie max-age.

    This was a URLSafeSerializer, where the signature never expires. `max_age` on
    set_cookie is only an instruction to the browser about when to stop sending the
    value — a copied cookie stayed valid indefinitely, including after signing out,
    because sign-out deletes the browser's copy and nothing more.
    """
    from itsdangerous import SignatureExpired

    from backend.api.deps import SESSION_COOKIE, SESSION_MAX_AGE, _serializer

    c = TestClient(app)
    c.post("/api/auth/signup",
           json={"handle": "session-expiry-user", "passphrase": "a long enough passphrase"})
    raw = c.cookies.get(SESSION_COOKIE)
    check("a session cookie was issued", bool(raw))

    check("the session has a bounded lifetime", SESSION_MAX_AGE <= 60 * 60 * 24 * 30,
          f"{SESSION_MAX_AGE}s")

    # The serializer must reject the very same token once it is older than the window.
    expired = False
    try:
        _serializer().loads(raw, max_age=-1)
    except SignatureExpired:
        expired = True
    check("an aged token is refused by the serializer itself", expired,
          "URLSafeSerializer would accept it forever; URLSafeTimedSerializer does not")

    # And the token still has to be intact.
    stolen = TestClient(app)
    stolen.cookies.set(SESSION_COOKIE, (raw or "") + "x")
    check("a tampered cookie is refused",
          stolen.get("/api/auth/me").status_code == 401)


def test_recovery_code_is_the_way_back_in_without_an_email() -> None:
    """A lost passphrase must not mean a lost journal, and must not require an email.

    The anonymity is the point — no email means no real identity on file and no reset
    link landing in an inbox another person can read, which matters for this product
    specifically. The cost of that is otherwise severe: forget the passphrase and months
    of somebody's writing are gone for good.

    A code issued once at sign-up closes that gap without reopening the other one. The
    properties that make it safe are all asserted here.
    """
    handle = "recovery-flow-user"
    first = TestClient(app).post(
        "/api/auth/signup", json={"handle": handle, "passphrase": "a long enough passphrase"})
    check("signup succeeds", first.status_code == 201, first.text[:120])
    code = first.json().get("recovery_code")
    check("signup returns a recovery code", bool(code))
    check("the code is several words", len((code or "").split("-")) >= 4, str(code))

    locked = TestClient(app).post(
        "/api/auth/signin", json={"handle": handle, "passphrase": "the forgotten one"})
    check("the old passphrase no longer works for a stranger", locked.status_code == 401)

    used = TestClient(app).post("/api/auth/recover", json={
        "handle": handle, "recovery_code": (code or "").upper(),
        "passphrase": "a replacement passphrase"})
    check("the code resets the passphrase", used.status_code == 200, used.text[:160])
    check("entering the code is case-insensitive", used.status_code == 200)
    check("recovery signs the user in", "set-cookie" in used.headers)

    reissued = used.json().get("recovery_code")
    check("a fresh code is issued", bool(reissued) and reissued != code)

    replayed = TestClient(app).post("/api/auth/recover", json={
        "handle": handle, "recovery_code": code, "passphrase": "yet another passphrase"})
    check("the used code is consumed", replayed.status_code == 404,
          f"got {replayed.status_code} — a code that still works after a reset is a "
          f"second standing password on the account")

    now = TestClient(app).post(
        "/api/auth/signin", json={"handle": handle, "passphrase": "a replacement passphrase"})
    check("the new passphrase works", now.status_code == 200)

    # Wrong code and unknown handle must be indistinguishable, or this becomes a way of
    # asking whether somebody has an account here.
    wrong = TestClient(app).post("/api/auth/recover", json={
        "handle": handle, "recovery_code": "not-a-real-code-at-all-here",
        "passphrase": "a long enough passphrase"})
    nobody = TestClient(app).post("/api/auth/recover", json={
        "handle": "nobody-has-this-handle", "recovery_code": reissued,
        "passphrase": "a long enough passphrase"})
    check("a wrong code is refused", wrong.status_code == 404)
    check("an unknown handle fails identically",
          nobody.status_code == wrong.status_code and nobody.json() == wrong.json())

    # The plaintext must exist only in that one response.
    me = TestClient(app)
    me.post("/api/auth/signin",
            json={"handle": handle, "passphrase": "a replacement passphrase"})
    account = me.get("/api/auth/me").json()
    check("no recovery code is readable from the account",
          "recovery_code" not in account and "recovery_hash" not in account,
          str(sorted(account)))


def test_demo_signin_cannot_reach_a_real_account() -> None:
    """One-click demo entry, and the boundary that keeps it from being a back door.

    ``POST /api/demo/signin`` issues a session from a handle alone, so that seeing the
    demo needs no typing. That is only safe because it refuses anything not flagged
    ``is_demo``. Without that check it would be an unauthenticated way into any journal
    whose handle somebody guessed.

    It also has to fail *identically* for a real account and for a handle that does not
    exist. Different answers would turn it into a way of asking "does this person have
    an account here", which is the one disclosure this app exists to refuse.
    """
    real_handle = "demo-signin-real-user"
    owner = TestClient(app)
    r = owner.post("/api/auth/signup",
                   json={"handle": real_handle, "passphrase": "a long enough passphrase"})
    check("the real account was created", r.status_code == 201, r.text[:120])

    anon = TestClient(app)
    taken = anon.post("/api/demo/signin", json={"handle": real_handle})
    missing = anon.post("/api/demo/signin", json={"handle": "no-such-handle-anywhere"})

    check("demo sign-in refuses a real account", taken.status_code == 404,
          f"got {taken.status_code}")
    check("and an unknown handle fails the same way", missing.status_code == 404)
    check("the two responses are indistinguishable",
          taken.json() == missing.json(), f"{taken.json()} vs {missing.json()}")
    check("no session was issued", "set-cookie" not in taken.headers)

    listed = anon.get("/api/demo/characters")
    check("the character list is readable without signing in", listed.status_code == 200)
    check("and never contains a real account",
          all(c["handle"] != real_handle for c in listed.json()))


def test_the_nine_character_demo_creates_no_cross_account_links() -> None:
    """Nine demo accounts in one database, and no row in any of them touching another.

    The seeder is the only component in the codebase that legitimately holds every
    account open at once, which makes it the only one capable of creating the
    cross-account reference the product promises cannot exist. Nothing downstream would
    catch it: the store's guards and the route guards both scope by account_id and would
    simply return the wrong row's data as though it were yours.

    So the whole ecosystem is built into a throwaway database and checked directly. This
    also exercises every character file, so a malformed one fails here rather than on the
    hosted app.
    """
    import tempfile as _tf
    from pathlib import Path as _P

    from backend.seed_characters import (
        assert_no_cross_account_links, load_character_files, seed,
    )
    from backend.store import Store as _Store, StoreError as _StoreError

    fresh = _Store(_P(_tf.mkdtemp()) / "ecosystem.db")
    try:
        built = seed(fresh, reset=True)     # seed() calls the assertion itself
    except _StoreError as e:
        check("the nine characters build", False, str(e)[:300])
        return

    check("every character file built an account",
          len(built) == len(load_character_files()), f"{len(built)} accounts")
    check("the demo has nine characters", len(built) == 9, f"got {len(built)}")

    # Called again explicitly: seed() running it is the production path, and a test that
    # only trusts the thing under test to check itself is not much of a test.
    try:
        assert_no_cross_account_links(fresh)
        check("no row in any account references another account's row", True)
    except _StoreError as e:
        check("no row in any account references another account's row", False, str(e)[:300])

    # Two accounts holding an alias with the same string must still be unrelated rows.
    ids = sorted(built.values())
    rows = {}
    for aid in ids:
        for p in fresh.list_people(aid):
            rows.setdefault(p["alias"], []).append((aid, p["id"]))
    shared = {a: v for a, v in rows.items() if len(v) > 1}
    check("aliases are reused across accounts in this dataset", bool(shared),
          "nothing to prove isolation with")
    check("a repeated alias is a separate row in each account",
          all(len({pid for _, pid in v}) == len(v) for v in shared.values()))


def test_seeding_on_boot_is_opt_in_and_idempotent() -> None:
    """The hosted demo depends on this, so it is tested rather than assumed.

    A free hosting tier gives an ephemeral disk: the database is gone after every restart
    and redeploy. Seeding on boot is what stops a grader opening the link and finding an
    empty application. Three things have to hold:

      * it does NOT run unless asked, because on a laptop a surprise write at startup is
        the wrong default;
      * it DOES run when the host asks, on an empty disk;
      * running twice leaves the first one alone, so a restart with a real disk underneath
        neither duplicates the demo nor overwrites it.
    """
    from backend.api.deps import get_store
    from backend.seed_characters import load_character_files, passphrase_for

    first = load_character_files()[0]
    handle = first["handle"]

    before_path = os.environ["KRYTERIA_DB_PATH"]
    before_flag = os.environ.get("KRYTERIA_SEED_ON_BOOT")
    fresh = Path(tempfile.mkdtemp()) / "boot.db"

    def demo_exists() -> bool:
        return get_store().verify_account(handle, passphrase_for(handle)) is not None

    try:
        os.environ["KRYTERIA_DB_PATH"] = str(fresh)
        os.environ.pop("KRYTERIA_SEED_ON_BOOT", None)
        get_store.cache_clear()

        with TestClient(app):
            pass
        check("boot does not seed unless asked", not demo_exists())

        os.environ["KRYTERIA_SEED_ON_BOOT"] = "true"
        with TestClient(app):
            pass
        check("boot seeds the demo when the host asks", demo_exists())
        first_id = get_store().verify_account(handle, passphrase_for(handle))

        with TestClient(app):
            pass
        second_id = get_store().verify_account(handle, passphrase_for(handle))
        check("a second boot leaves the existing demo alone",
              second_id == first_id, f"{first_id} -> {second_id}")
    finally:
        os.environ["KRYTERIA_DB_PATH"] = before_path
        if before_flag is None:
            os.environ.pop("KRYTERIA_SEED_ON_BOOT", None)
        else:
            os.environ["KRYTERIA_SEED_ON_BOOT"] = before_flag
        get_store.cache_clear()


def test_the_hosted_configuration_signs_in_over_https_and_only_https() -> None:
    """The exact deployed setup: Secure cookies on, behind https.

    This is pinned because the failure it guards against is silent and catastrophic in
    opposite directions.

    With ``KRYTERIA_SECURE_COOKIES=true`` the session cookie carries the Secure flag, so
    a browser will not send it back over plain http. That is the point of the flag — a
    session cookie for a relationship journal has no business travelling in clear text.
    But it also means a deployment that terminates as http would let somebody sign in
    successfully and then 401 on the very next request, which looks like a broken login
    rather than a misconfigured scheme.

    So both halves are asserted: it works over https, and it does NOT work over http.
    Dropping the Secure flag would pass the first and fail the second.
    """
    before = os.environ.get("KRYTERIA_SECURE_COOKIES")
    os.environ["KRYTERIA_SECURE_COOKIES"] = "true"
    try:
        handle = "hosted-config-user"
        signup = TestClient(app, base_url="https://testserver")
        r = signup.post("/api/auth/signup",
                        json={"handle": handle, "passphrase": "a long enough passphrase"})
        check("signup works over https", r.status_code == 201, r.text[:120])

        secure = TestClient(app, base_url="https://testserver")
        r = secure.post("/api/auth/signin",
                        json={"handle": handle, "passphrase": "a long enough passphrase"})
        check("signin works over https", r.status_code == 200)
        check("the cookie carries the Secure flag",
              "secure" in r.headers.get("set-cookie", "").lower())
        check("and the session is usable over https",
              secure.get("/api/profiles").status_code == 200)

        plain = TestClient(app, base_url="http://testserver")
        plain.post("/api/auth/signin",
                   json={"handle": handle, "passphrase": "a long enough passphrase"})
        check("a Secure cookie is not replayed over plain http",
              plain.get("/api/profiles").status_code == 401)
    finally:
        if before is None:
            os.environ.pop("KRYTERIA_SECURE_COOKIES", None)
        else:
            os.environ["KRYTERIA_SECURE_COOKIES"] = before


def test_demo_reset_refuses_a_real_account() -> None:
    c = new_client("not-the-demo")
    r = c.post("/api/demo/reset")
    check("reset refuses a real account", r.status_code == 403, f"got {r.status_code}")
    check("and says why", "real account" in r.json()["detail"])


def test_health_states_what_this_deployment_keeps() -> None:
    """A grader, an operator and the sign-up screen all read the same field."""
    r = TestClient(app).get("/api/health")
    body = r.json()
    check("health answers anonymously", r.status_code == 200)
    check("it says whether storage is durable", "storage_durable" in body)
    check("and says it in words too", bool(body.get("storage_note")))
    check("the note matches the flag",
          ("erased" in body["storage_note"]) is not body["storage_durable"],
          str(body.get("storage_durable")))


def test_pasting_a_list_shows_it_back_before_it_saves_anything() -> None:
    """Parse and create are two endpoints so she sees the parse before it lands."""
    c = new_client("paster")
    text = ("Financial independence — takes responsibility for his own obligations\n"
            "- Emotional availability: says how he feels\n"
            "Makes me laugh\n")

    r = c.post("/api/criteria/parse", json={"text": text})
    check("parse answers", r.status_code == 200, f"got {r.status_code}")
    body = r.json()
    check("it read three lines", body["ready"] == 3, str(body["ready"]))
    check("PARSING SAVED NOTHING", c.get("/api/criteria").json() == [])

    r = c.post("/api/criteria/bulk", json={"items": [
        {"value": l["value"], "desired_behavior": l["desired_behavior"]}
        for l in body["lines"]]})
    check("bulk create answers 201", r.status_code == 201, f"got {r.status_code}")
    check("it reports what it made", r.json()["created"] == 3)
    library = c.get("/api/criteria").json()
    check("all three are in the library", len(library) == 3, str(len(library)))
    laugh = next(x for x in library if x["value"] == "Makes me laugh")
    check("a name with no behaviour went in as a name with no behaviour",
          laugh["desired_behavior"] == "")

    # A second paste of the same list is reported, not silently doubled.
    again = c.post("/api/criteria/parse", json={"text": text}).json()
    check("the re-paste is all duplicates", again["ready"] == 0, str(again["ready"]))
    check("and each one names what it matched",
          all(l["duplicate_of"] for l in again["lines"]))

    check("an empty paste is refused",
          c.post("/api/criteria/parse", json={"text": ""}).status_code == 422)


def test_add_all_fills_a_profile_without_deciding_what_matters() -> None:
    c = new_client("adder")
    c.post("/api/criteria/bulk", json={"items": [
        {"value": "Kindness"}, {"value": "Ambition"}, {"value": "Humour"}]})
    prof = c.post("/api/profiles", json={"name": "Partner KRYteria"}).json()
    library = c.get("/api/criteria").json()
    c.post(f"/api/profiles/{prof['id']}/criteria",
           json={"criterion_id": library[0]["id"], "tier": "mandatory"})

    r = c.post(f"/api/profiles/{prof['id']}/criteria/bulk", json={})
    check("add-all answers 201", r.status_code == 201, f"got {r.status_code}")
    body = r.json()
    check("it added the two that were missing", body["added"] == 2, str(body))
    check("and said the third was already there", body["already_there"] == 1)

    rows = {x["value"]: x for x in body["criteria"]}
    check("the profile now holds all three", len(rows) == 3)
    check("the chosen tier survived", rows[library[0]["value"]]["tier"] == "mandatory")
    check("and nothing new was made Mandatory",
          all(v["tier"] == "preferred" for k, v in rows.items()
              if k != library[0]["value"]))

    again = c.post(f"/api/profiles/{prof['id']}/criteria/bulk", json={}).json()
    check("running it again is a no-op", again["added"] == 0, str(again))


def test_account_creation_is_bounded_for_the_application_as_a_whole() -> None:
    """A fresh handle every time used to meet no limit at all.

    The per-handle counter is cleared by a successful sign-up, so a script that never
    reuses a handle was never slowed down — and about seventeen new accounts exhaust the
    2,000,000-token global daily budget, after which KRYteria analyses nothing for
    anybody. The money was never the exposure (that cap holds the worst day to roughly a
    dollar); the availability was.

    The three properties below are the whole argument for a limiter that has no key.
    A keyless bound is itself a denial-of-service primitive, so what matters is that
    tripping it costs a visitor very little and costs an existing user nothing.
    """
    from backend import throttle

    throttle.reset()
    c = TestClient(app)

    codes = [
        c.post("/api/auth/signup",
               json={"handle": f"flood-{i}", "passphrase": "a long enough passphrase"}
               ).status_code
        for i in range(throttle.MAX_NEW_ACCOUNTS_PER_HOUR)
    ]
    check("the hourly allowance is actually spendable",
          codes == [201] * throttle.MAX_NEW_ACCOUNTS_PER_HOUR,
          f"got {sorted(set(codes))} — a genuine visitor must not meet this")

    r = c.post("/api/auth/signup",
               json={"handle": "flood-over", "passphrase": "a long enough passphrase"})
    check("one more is refused", r.status_code == 429, f"got {r.status_code}")
    check("and it says how long to wait", "retry-after" in
          {k.lower() for k in r.headers}, str(dict(r.headers)))

    # Property 1: it refuses CREATION, never ACCESS. Everybody already using the app is
    # unaffected — this is what keeps the limiter from being worse than what it prevents.
    signin = c.post("/api/auth/signin",
                    json={"handle": "flood-0", "passphrase": "a long enough passphrase"})
    check("an existing account can still sign in while it is tripped",
          signin.status_code == 200, f"got {signin.status_code}")

    # Property 2: a 409 creates nothing, so it must not spend the allowance. Otherwise
    # anybody could close the door for everyone else without opening it once.
    throttle.reset()
    taken = c.post("/api/auth/signup",
                   json={"handle": "flood-0", "passphrase": "a long enough passphrase"})
    check("re-using a handle still conflicts", taken.status_code == 409,
          f"got {taken.status_code}")
    after = c.post("/api/auth/signup",
                   json={"handle": "flood-fresh", "passphrase": "a long enough passphrase"})
    check("a refused sign-up did not consume the allowance",
          after.status_code == 201, f"got {after.status_code}")

    # Property 3: the day bound exists so a patient script cannot trickle under the hour
    # bound forever, which is the gap an hourly-only limit leaves open.
    check("there is a daily bound as well as an hourly one",
          throttle.MAX_NEW_ACCOUNTS_PER_DAY > throttle.MAX_NEW_ACCOUNTS_PER_HOUR,
          "an hourly limit alone is trickle-able")

    throttle.reset()


def test_an_entry_with_no_criteria_says_so_instead_of_going_quiet() -> None:
    """The silence was the defect, not the short answer.

    From the 19 November user test. With no criteria the Evidence agent never runs —
    there is nothing to map an observation against — so an entry comes back as extracted
    observations and nothing else. The tester read that as "the analysis feature has not
    been built yet" and asked for it, which is the product he was already using.

    What must hold: the entry is still saved, the short analysis still happens, and the
    response *says why it is short*. The honest sentence is the same move as
    `analysis_withheld` on a safety halt — this app states what it is not doing rather
    than letting somebody infer it.
    """
    c = new_client("not-yet-user")

    r = c.post("/api/brain-dump", json={
        "text": "Sam cancelled again on Friday, the third time this month. He said work "
                "ran over. I keep telling myself it is fine.",
        "retention": "keep_all",
    })
    check("the entry is accepted", r.status_code == 201, f"got {r.status_code}: {r.text[:200]}")
    body = r.json()
    check("and it is saved", bool(body.get("entry", {}).get("id")))

    analysis = body.get("analysis") or {}
    check("no evidence was produced, because there is nothing to map to",
          not analysis.get("mappings"), str(analysis.get("mappings"))[:120])
    not_yet = analysis.get("not_yet")
    check("the response says WHY it is short", bool(not_yet), str(analysis.keys()))
    if not_yet:
        check("it names the reason machine-readably",
              not_yet.get("reason") == "no_criteria", str(not_yet.get("reason")))
        check("and tells the person what to do about it",
              "matters to you" in not_yet.get("message", ""), not_yet.get("message", ""))

    # And it must disappear once there is something to judge against — a permanent
    # "we can't help you yet" on an account that has set its standards would be worse
    # than the silence it replaced.
    c.post("/api/criteria", json={"value": "Reliability",
                                  "desired_behavior": "Does what he says he will"})
    r2 = c.post("/api/brain-dump", json={
        "text": "He said he would call on Sunday and he did.", "retention": "keep_all"})
    check("a second entry, now that a criterion exists, carries no not_yet",
          r2.status_code == 201 and not (r2.json().get("analysis") or {}).get("not_yet"),
          str((r2.json().get("analysis") or {}).get("not_yet")))


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
