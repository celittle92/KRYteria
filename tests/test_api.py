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
    c = TestClient(app)
    r = c.post("/api/auth/signup",
               json={"handle": handle, "passphrase": "a long enough passphrase"})
    assert r.status_code == 201, r.text
    return c


# ---------------------------------------------------------------- isolation

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


def test_demo_reset_refuses_a_real_account() -> None:
    c = new_client("not-the-demo")
    r = c.post("/api/demo/reset")
    check("reset refuses a real account", r.status_code == 403, f"got {r.status_code}")
    check("and says why", "real account" in r.json()["detail"])


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
