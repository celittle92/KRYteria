"""Persistence for KRYteria. Every agent tool reaches the database through this module.

Three of the product's promises are enforced here, in code, rather than asked for in a
prompt — because a prompt is a request and a rule in code cannot be argued with by a
journal entry:

  1. **A pattern cannot exist without the entries that support it.** ``save_pattern``
     refuses an empty evidence list and recomputes ``support_count`` from the distinct
     entries it was actually given, rather than trusting the number the model reported.

  2. **Thin evidence cannot be called a pattern.** Below ``MIN_SUPPORT`` distinct
     supporting entries, ``evidence_strength`` is forced to ``insufficient`` whatever the
     model claimed. The finding still gets written and still gets shown — "I don't have
     enough to say" is a result the user is entitled to see, not an empty state to hide.

  2b. **A confident finding must admit another reading.** ``moderate`` and ``strong``
     findings are refused without at least one alternative explanation. A finding with no
     alternatives is a verdict wearing a finding's clothes, and this product does not issue
     verdicts about anybody.

  3. **Criteria are never overwritten.** ``revise_criterion`` inserts a new version and
     supersedes the old row. There is no code path that mutates a criterion's text, because
     "my standards quietly got easier to meet" is one of the most valuable things this app
     can show somebody, and an UPDATE destroys it.
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
import uuid
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
SCHEMA_PATH = BACKEND_DIR / "schema.sql"
DEFAULT_DB_PATH = PROJECT_DIR / "data" / "kryteria.db"

#: Bump whenever schema.sql changes shape. An existing database with a different version
#: is refused at open time with the command to rebuild it, rather than failing later with
#: "no such column" somewhere unrelated.
SCHEMA_VERSION = "2026-11-12.1"

#: Distinct journal entries needed before a finding may be called a pattern.
#: Two points make a line and not a trend; the mockups' own example rests on three.
MIN_SUPPORT = 3

#: How many times a user may postpone the same concern before the Reflection agent is
#: allowed to ask the signature question. Never a shaming threshold — it changes which
#: question is asked, nothing else.
POSTPONEMENT_PROBE_AT = 3

OBSERVATION_KINDS = (
    "reported_event",
    "interpretation",
    "emotional_reaction",
    "missing_information",
    "uncertainty",
)

DECISION_CHOICES = (
    "talk",
    "boundary",
    "more_time",
    "gather_info",
    "reconsider",
    "revise_criterion",
    "undecided",
)

#: V1 ships Clarity Mode only; Tough Love is V2 and not an MVP priority. Tone changes
#: presentation, never reasoning, evidence, or an assessment outcome.
TONE_MODES = ("clarity", "tough_love")

#: What KRYteria keeps once a brain dump has been processed.
#:
#:   discard        the narrative and everything derived from it go
#:   analysis_only  the narrative is erased; observations and mappings survive
#:   keep_all       everything stays until the user deletes it
#:
#: ``analysis_only`` is the default. Keeping the intimate original by default would make
#: the most sensitive thing in the product the thing that requires an opt-out.
RETENTION_MODES = ("discard", "analysis_only", "keep_all")

#: What was seen against one behavioural indicator. Four states, not a checkbox —
#: "no opportunity to observe" is not the same as "looked and it wasn't there".
CHECKLIST_STATES = ("observed", "not_observed", "contradicted", "no_opportunity")

#: Abuse categories the safety layer recognises. They overlap, and abuse can be a pattern,
#: a single serious incident, or both.
SAFETY_CATEGORIES = ("physical", "emotional_psychological", "sexual", "coercive_control",
                     "stalking_harassment", "self_harm", "not_applicable")

#: Ordered least to most serious — ``should_offer_resources`` compares by index, so the
#: order is load-bearing, not cosmetic.
CONCERN_LEVELS = ("potential", "pattern", "disclosure", "immediate_danger")

#: The dimension a follow-up question is probing. Keeps Evidence Interrogation to the
#: gaps that actually change an assessment.
GAP_KINDS = ("frequency", "pattern", "magnitude", "communication", "circumstances",
             "accountability", "impact", "definition", "comparison")

#: Dimension 1 of the KRYteria system — how much a criterion matters to the user.
TIERS = ("mandatory", "preferred", "aspirational")

#: Dimension 2 — what is known about one person against one criterion. ``unknown`` is the
#: default and an honest answer, not an empty state.
#: ``not_applicable`` is a real answer and is never treated as pass, fail, or missing
#: information. "Wants children" can be Mandatory under one profile and Not Applicable
#: under another; neither reading contaminates the other.
ASSESSMENT_STATUSES = ("pass", "unknown", "fail", "not_applicable")

#: How a piece of evidence relates to a criterion. ``complicating`` is load-bearing:
#: collapsing it into supporting/contradicting forces a verdict the evidence does not
#: support.
EVIDENCE_RELATIONS = ("supporting", "contradicting", "complicating", "unrelated")

#: Epistemic level. A contextual hypothesis must never carry the authority of a finding.
SOURCE_LEVELS = ("established_research", "research_informed", "agent_hypothesis",
                 "user_stated")

#: Qualitative only. The brief is explicit and so is the PRD: never a numerical
#: relationship score. There is no code path in this module that produces a number
#: describing a person or a relationship.
EVIDENCE_STRENGTHS = ("insufficient", "limited", "moderate", "strong")

#: Strengths at or above which a finding must offer an alternative explanation.
STRENGTHS_REQUIRING_ALTERNATIVES = ("moderate", "strong")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


class StoreError(RuntimeError):
    """A rule this module enforces was broken. Not a database failure."""


class NotOwned(StoreError):
    """A row was reached that does not belong to the account asking for it.

    Raised rather than returning empty, so a caller that forgot to scope a query fails
    loudly in development instead of silently reading nothing — or, worse, something.

    The HTTP layer turns this into 404, never 403: confirming a row exists but belongs to
    somebody else is itself a disclosure, and in this application that disclosure could
    tell one person that another person is journalling about them.
    """


_CREATE_TABLE = re.compile(
    r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\n\);", re.DOTALL | re.IGNORECASE
)


def _declared_columns(schema_sql: str) -> dict[str, set[str]]:
    """Column names schema.sql declares, per table.

    A deliberately simple parser: it reads the first identifier of each line inside a
    CREATE TABLE body and skips table-level constraints. It only needs to be right about
    column *names*, because its one job is spotting a column the live database lacks.
    """
    tables: dict[str, set[str]] = {}
    for name, body in _CREATE_TABLE.findall(schema_sql):
        columns: set[str] = set()
        for raw in body.split("\n"):
            line = raw.strip()
            if not line or line.startswith("--"):
                continue
            first = line.split()[0].strip(",").strip()
            if first.upper() in {
                "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "CONSTRAINT", ")",
            }:
                continue
            if first.isidentifier():
                columns.add(first)
        if columns:
            tables[name] = columns
    return tables


def _missing_columns(conn: sqlite3.Connection, schema_sql: str) -> list[tuple[str, str]]:
    """Columns schema.sql declares that the live database does not have."""
    missing: list[tuple[str, str]] = []
    for table, declared in _declared_columns(schema_sql).items():
        try:
            live = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        except sqlite3.OperationalError:
            continue
        if not live:
            continue
        missing.extend((table, c) for c in sorted(declared - live))
    return missing


# --------------------------------------------------------------------- connection


class Store:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def read(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def write(self):
        """One all-or-nothing transaction. Either the whole change lands or none of it."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # ----------------------------------------------------------------- ownership
    #
    # Privacy is enforced HERE as well as in the API layer, deliberately. The API's
    # ownership guards are the first line; these are the one that holds when somebody
    # adds a route and forgets. For an application where a leak would tell one person
    # that another is journalling about them, one line of defence is not enough.

    @staticmethod
    def _owns(conn: sqlite3.Connection, table: str, row_id: int, account_id: int,
              *, via: str | None = None) -> bool:
        """Does ``account_id`` own this row? ``via`` names a table to join through."""
        if via:
            sql = (f"SELECT 1 FROM {table} t JOIN {via} p ON p.id = t.{via[:-1]}_id"
                   f" WHERE t.id = ? AND p.account_id = ?")
        else:
            sql = f"SELECT 1 FROM {table} WHERE id = ? AND account_id = ?"
        return conn.execute(sql, (row_id, account_id)).fetchone() is not None

    def _assert_owns(self, conn: sqlite3.Connection, table: str, row_id: int,
                     account_id: int, *, via: str | None = None) -> None:
        if not self._owns(conn, table, row_id, account_id, via=via):
            raise NotOwned(f"No {table[:-1]} {row_id} for this account.")

    def _init_schema(self) -> None:
        """Create the schema, and refuse to run against a stale database.

        ``CREATE TABLE IF NOT EXISTS`` silently does nothing to a table that already
        exists, so a database created before a column was added keeps the old shape and
        fails later with an unhelpful ``no such column``. This catches that at open time
        and says what to do about it.

        There is no migration framework yet, and with no real users that is the right
        trade — but it is a real gap, and it needs Alembic or equivalent before anybody's
        journal depends on it.
        """
        conn = self._connect()
        try:
            # Was this database already populated before we touched it? Checked BEFORE
            # the script runs, because executescript creates the tables and would make
            # every database look brand new.
            pre_existing = conn.execute(
                "SELECT COUNT(*) AS n FROM sqlite_master WHERE type = 'table'"
            ).fetchone()["n"] > 0
            found = None
            if pre_existing:
                try:
                    row = conn.execute(
                        "SELECT value FROM schema_meta WHERE key = 'version'"
                    ).fetchone()
                    found = row["value"] if row else "pre-versioning"
                except sqlite3.OperationalError:
                    found = "pre-versioning"

            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

            # Checked BEFORE running the script, because an index declared over a column
            # the old table lacks makes executescript itself fail with a bare
            # "no such column" — which is the unhelpful error this guard exists to
            # replace. A brand-new database has no tables, so nothing is missing.
            #
            # The version stamp alone is not enough either: a stamp can be written to a
            # database whose tables are already the wrong shape. The columns are what
            # matter, so drift is caught however it arose.
            missing = _missing_columns(conn, schema_sql) if pre_existing else []
            if missing or (found not in (None, SCHEMA_VERSION)):
                detail = ""
                if missing:
                    shown = ", ".join(f"{t}.{c}" for t, c in missing[:6])
                    more = f" (and {len(missing) - 6} more)" if len(missing) > 6 else ""
                    detail = f"\nMissing columns: {shown}{more}"
                raise StoreError(
                    f"{self.db_path} does not match the current schema "
                    f"({SCHEMA_VERSION}). KRYteria has no migrations yet.{detail}\n\n"
                    f"  rm {self.db_path}*\n"
                    f"  .venv/bin/python -m backend.seed_demo\n\n"
                    "Nothing of value is lost: that command rebuilds the demo account. "
                    "If this database holds real journal entries, export them first "
                    "with GET /api/export."
                )

            try:
                conn.executescript(schema_sql)
            except sqlite3.OperationalError as e:
                # Backstop for drift the column check cannot see, such as a changed
                # CHECK constraint. Still better than a bare SQL error.
                raise StoreError(
                    f"{self.db_path} could not be brought up to the current schema "
                    f"({SCHEMA_VERSION}): {e}\n\n"
                    f"  rm {self.db_path}*\n"
                    f"  .venv/bin/python -m backend.seed_demo"
                ) from e

            if found is None:
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
                    (SCHEMA_VERSION,),
                )
        finally:
            conn.close()

    # ----------------------------------------------------------------- accounts

    def create_account(
        self, handle: str, passphrase: str, *, is_demo: bool = False
    ) -> int:
        """Anonymous account. ``handle`` is user-chosen and is not an email or a name."""
        from .security import hash_passphrase

        handle = handle.strip()
        if not handle:
            raise StoreError("A handle is required.")
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO accounts (handle, passphrase_hash, is_demo, created_at) "
                "VALUES (?, ?, ?, ?)",
                (handle, hash_passphrase(passphrase), int(is_demo), _now()),
            )
            return int(cur.lastrowid)

    def verify_account(self, handle: str, passphrase: str) -> int | None:
        """Returns the account id, or None. Never returns or logs the stored hash."""
        from .security import verify_passphrase

        with self.read() as conn:
            row = conn.execute(
                "SELECT id, passphrase_hash FROM accounts WHERE handle = ?",
                (handle.strip(),),
            ).fetchone()
        if row is None:
            # Spend the same work on a missing handle as on a wrong passphrase, so the
            # response time does not reveal which handles exist.
            verify_passphrase(passphrase, None)
            return None
        if verify_passphrase(passphrase, row["passphrase_hash"]):
            with self.write() as conn:
                conn.execute(
                    "UPDATE accounts SET last_seen_at = ? WHERE id = ?", (_now(), row["id"])
                )
            return int(row["id"])
        return None

    def get_account(self, account_id: int) -> dict[str, Any] | None:
        with self.read() as conn:
            row = conn.execute(
                "SELECT id, handle, tone_mode, theme, resource_offering, retention,"
                " timezone, region, is_demo, created_at, last_seen_at"
                " FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_preferences(
        self, account_id: int, *, tone_mode: str | None = None, theme: str | None = None,
        resource_offering: str | None = None, retention: str | None = None,
        region: str | None = None,
    ) -> None:
        """Change a preference. ``region`` is the user's own statement of where they are.

        Pass ``""`` to clear it. It is never inferred, and clearing it must always work:
        somebody who has moved, or who told us once and would rather not have, is
        entitled to take it back.
        """
        if region:
            region = region.strip().upper()
            if region != "GLOBAL" and not (len(region) == 2 and region.isalpha()):
                raise StoreError(
                    f"region must be a two-letter ISO 3166-1 country code or 'GLOBAL', "
                    f"got {region!r}. A free-text location is both less useful for "
                    "matching a directory and more identifying to store."
                )
        if tone_mode and tone_mode not in TONE_MODES:
            raise StoreError(f"Unknown tone mode: {tone_mode}")
        if theme and theme not in ("dark", "warm"):
            raise StoreError(f"Unknown theme: {theme}")
        if resource_offering and resource_offering not in (
            "proactive", "on_request", "suppressed"
        ):
            raise StoreError(f"Unknown resource_offering: {resource_offering}")
        if retention and retention not in RETENTION_MODES:
            raise StoreError(f"Unknown retention: {retention}")
        with self.write() as conn:
            for column, value in (("tone_mode", tone_mode), ("theme", theme),
                                  ("resource_offering", resource_offering),
                                  ("retention", retention)):
                if value:
                    conn.execute(
                        f"UPDATE accounts SET {column} = ? WHERE id = ?",
                        (value, account_id),
                    )
            # region is handled separately because "" means CLEAR IT, and the loop above
            # treats a falsy value as "leave alone". Being unable to withdraw a location
            # you once gave is not an acceptable shape for this field.
            if region is not None:
                conn.execute("UPDATE accounts SET region = ? WHERE id = ?",
                             (region or None, account_id))

    def delete_account(self, account_id: int) -> None:
        """Remove everything. Rows are deleted, not flagged.

        ``ON DELETE CASCADE`` carries this through every child table. The PRD promises the
        user control over their data; a soft delete would make that promise false.
        """
        with self.write() as conn:
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))

    # ----------------------------------------------------------------- domains

    def create_domain(self, account_id: int, name: str, kind: str) -> int:
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO domains (account_id, name, kind, created_at) VALUES (?, ?, ?, ?)",
                (account_id, name.strip(), kind, _now()),
            )
            return int(cur.lastrowid)

    def list_domains(self, account_id: int, *, include_archived: bool = False):
        sql = "SELECT * FROM domains WHERE account_id = ?"
        if not include_archived:
            sql += " AND archived_at IS NULL"
        sql += " ORDER BY created_at"
        with self.read() as conn:
            return [dict(r) for r in conn.execute(sql, (account_id,))]

    # ----------------------------------------------------------------- people

    def upsert_person(
        self, account_id: int, alias: str, *, domain_id: int | None = None,
        role_label: str | None = None,
    ) -> int:
        """People exist only as aliases the user chose. There is no real-name column."""
        alias = alias.strip()
        if not alias:
            raise StoreError("An alias is required.")
        with self.write() as conn:
            row = conn.execute(
                "SELECT id FROM people WHERE account_id = ? AND alias = ?",
                (account_id, alias),
            ).fetchone()
            if row:
                return int(row["id"])
            cur = conn.execute(
                "INSERT INTO people (account_id, domain_id, alias, role_label, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (account_id, domain_id, alias, role_label, _now()),
            )
            return int(cur.lastrowid)

    def person_footprint(self, account_id: int, person_id: int) -> dict[str, Any]:
        """What removing this person would take with them.

        Shown before the deletion, not after. Somebody removing a person from a journal
        like this may be doing it after a breakup, or for their own safety — either way
        they are entitled to know what disappears before it does.
        """
        with self.read() as conn:
            self._assert_owns(conn, "people", person_id, account_id)
            counts = {
                "entries": conn.execute(
                    "SELECT COUNT(*) AS n FROM entry_people ep JOIN entries e"
                    " ON e.id = ep.entry_id WHERE ep.person_id = ?"
                    " AND e.deleted_at IS NULL", (person_id,)
                ).fetchone()["n"],
                "assessments": conn.execute(
                    "SELECT COUNT(*) AS n FROM assessments WHERE person_id = ?",
                    (person_id,)
                ).fetchone()["n"],
                "evidence_links": conn.execute(
                    "SELECT COUNT(*) AS n FROM evidence_links WHERE person_id = ?",
                    (person_id,)
                ).fetchone()["n"],
            }
        return counts

    def delete_person(self, account_id: int, person_id: int,
                      *, delete_entries: bool = False) -> dict[str, Any]:
        """Remove a person.

        Their **assessments always go** — a Pass or Fail is about them specifically and
        means nothing without them.

        Their **entries survive by default**, because an entry is the user's own writing
        about their own life, and losing a month of journal because somebody tidied up a
        name would be a cruel default. ``delete_entries=True`` removes those too, for
        when the point is that nothing about them remains.
        """
        footprint = self.person_footprint(account_id, person_id)
        removed_entries = 0

        with self.write() as conn:
            if delete_entries:
                rows = conn.execute(
                    "SELECT entry_id FROM entry_people WHERE person_id = ?", (person_id,)
                ).fetchall()
                for row in rows:
                    conn.execute(
                        "DELETE FROM entries WHERE id = ? AND account_id = ?",
                        (row["entry_id"], account_id),
                    )
                    removed_entries += 1
            # Cascades handle entry_people, assessments and proposals; evidence_links
            # keep the entry and lose only the person reference.
            conn.execute("DELETE FROM people WHERE id = ? AND account_id = ?",
                         (person_id, account_id))

        return {
            "assessments_removed": footprint["assessments"],
            "entries_removed": removed_entries,
            "entries_kept": 0 if delete_entries else footprint["entries"],
        }

    def list_people(self, account_id: int):
        with self.read() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM people WHERE account_id = ? ORDER BY alias", (account_id,)
                )
            ]

    # ----------------------------------------------------------------- criteria

    def create_criterion(
        self,
        account_id: int,
        *,
        value: str,
        desired_behavior: str,
        why_it_matters: str | None = None,
        examples: Sequence[str] = (),
    ) -> int:
        """Add a standard to the Master Criteria Library.

        A criterion here carries no tier and belongs to no profile — the same standard
        matters differently depending on what the user is looking for.

        There is deliberately no validation of whether a criterion is *reasonable*.
        "Soft hands" is as valid a row as "Compatible relationship intentions". KRYteria
        does not judge what matters to somebody; it helps them apply it consistently.
        """
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO criteria (account_id, lineage_id, version, value,"
                " desired_behavior, why_it_matters, examples_json, status, created_at)"
                " VALUES (?, ?, 1, ?, ?, ?, ?, 'active', ?)",
                (
                    account_id, uuid.uuid4().hex, value.strip(),
                    desired_behavior.strip(), why_it_matters,
                    json.dumps(list(examples)), _now(),
                ),
            )
            return int(cur.lastrowid)

    # ----------------------------------------------------------------- profiles

    def create_profile(
        self, account_id: int, name: str, *, objective: str | None = None,
        context_label: str | None = None, domain_id: int | None = None,
    ) -> int:
        """A saved configuration for one relationship objective.

        No profile ranks above another. Nothing in this module treats a long-term profile
        as the real one or failing it as a defect.
        """
        name = name.strip()
        if not name:
            raise StoreError("A profile needs a name.")
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO profiles (account_id, domain_id, name, objective,"
                " context_label, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (account_id, domain_id, name, objective, context_label, _now()),
            )
            return int(cur.lastrowid)

    def list_profiles(self, account_id: int, *, include_archived: bool = False):
        sql = "SELECT * FROM profiles WHERE account_id = ?"
        if not include_archived:
            sql += " AND archived_at IS NULL"
        sql += " ORDER BY sort_order, created_at"
        with self.read() as conn:
            return [dict(r) for r in conn.execute(sql, (account_id,))]

    def update_profile(self, account_id: int, profile_id: int, *,
                       name: str | None = None, objective: str | None = None,
                       context_label: str | None = None) -> None:
        """Rename a profile, or change what it is for.

        Christine, 2026-11-12: *"users may want to adjust their profiles… as their
        dating lives change."* They will — a "Boyfriend KRYteria" becomes a "Husband
        KRYteria", or the name stops fitting the person who wrote it. Nothing about the
        configuration is invalidated by a rename, so this touches the label only and
        leaves every criterion, tier, assessment and history row where it is.
        """
        fields: list[tuple[str, Any]] = []
        if name is not None:
            if not name.strip():
                raise StoreError("A profile needs a name.")
            fields.append(("name", name.strip()))
        if objective is not None:
            fields.append(("objective", objective.strip() or None))
        if context_label is not None:
            fields.append(("context_label", context_label.strip() or None))
        if not fields:
            return
        with self.write() as conn:
            self._assert_owns(conn, "profiles", profile_id, account_id)
            try:
                conn.execute(
                    f"UPDATE profiles SET {', '.join(f'{k} = ?' for k, _ in fields)},"
                    " updated_at = ? WHERE id = ?",
                    [v for _, v in fields] + [_now(), profile_id],
                )
            except sqlite3.IntegrityError:
                raise StoreError(f"You already have a profile called {name!r}.") from None

    def set_profile_archived(self, account_id: int, profile_id: int,
                             archived: bool) -> None:
        """Hide a profile without destroying what it recorded. Reversible.

        The default way to get rid of one. A profile that no longer describes anybody's
        life still holds the assessments made under it, and those are the record of what
        the user thought at the time — which is the thing this product exists to keep.
        """
        with self.write() as conn:
            self._assert_owns(conn, "profiles", profile_id, account_id)
            conn.execute("UPDATE profiles SET archived_at = ?, updated_at = ?"
                         " WHERE id = ?",
                         (_now() if archived else None, _now(), profile_id))

    # NO per-profile hard delete, deliberately. Christine, 2026-11-12: "oh maybe it
    # should just be an archive then. no deletion."
    #
    # Right, and it matches everything else here: criteria are versioned rather than
    # overwritten, assessment history keeps every transition, and a pattern must cite
    # the entries it rests on. A profile holds the assessments made under it -- the
    # record of what somebody thought at the time -- and nine tables reference it, most
    # cascading. "Delete this profile" would quietly take all of that, and nobody can
    # consent to that from the word "delete" alone.
    #
    # The genuine need to erase is already met, at the level where it belongs:
    # `delete_account` removes everything, irreversibly, on explicit confirmation.

    def add_criterion_to_profile(
        self, account_id: int, profile_id: int, criterion_id: int, *,
        tier: str = "preferred", relevance: str = "relevant",
        copied_from_profile_id: int | None = None,
    ) -> int:
        """Select a library criterion into a profile, with this profile's own tier."""
        if tier not in TIERS:
            raise StoreError(f"tier must be one of {TIERS}, got {tier!r}")
        if relevance not in ("relevant", "not_applicable"):
            raise StoreError(f"Unknown relevance: {relevance!r}")
        with self.write() as conn:
            self._assert_owns(conn, "profiles", profile_id, account_id)
            self._assert_owns(conn, "criteria", criterion_id, account_id)
            cur = conn.execute(
                "INSERT INTO profile_criteria (profile_id, criterion_id, tier, relevance,"
                " copied_from_profile_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (profile_id, criterion_id, tier, relevance, copied_from_profile_id, _now()),
            )
            return int(cur.lastrowid)

    def set_profile_tier(self, account_id: int, profile_id: int, criterion_id: int,
                         tier: str) -> None:
        """Change a criterion's tier **in this profile only**."""
        if tier not in TIERS:
            raise StoreError(f"tier must be one of {TIERS}, got {tier!r}")
        with self.write() as conn:
            self._assert_owns(conn, "profiles", profile_id, account_id)
            conn.execute(
                "UPDATE profile_criteria SET tier = ? WHERE profile_id = ?"
                " AND criterion_id = ?",
                (tier, profile_id, criterion_id),
            )

    def set_profile_relevance(self, account_id: int, profile_id: int,
                              criterion_id: int, relevance: str) -> None:
        """Mark a criterion relevant, or not, **in this profile only**.

        Christine, 2026-11-12: *"in ONS KRYteria, 'Compatible Relationship Intentions'
        could be applicable. Someone may not want a ONS with someone who wants a
        relationship."* Exactly so — and it is the clearest possible illustration of why
        relevance belongs to the profile rather than to the criterion. Whether wanting
        the same thing matters here is the user's call, not a property of the encounter
        type, and certainly not ours to fix at seed time.

        Changing it here never touches another profile, for the same reason tiers do
        not: the configurations are independent.
        """
        if relevance not in ("relevant", "not_applicable"):
            raise StoreError(
                f"relevance must be 'relevant' or 'not_applicable', got {relevance!r}")
        with self.write() as conn:
            self._assert_owns(conn, "profiles", profile_id, account_id)
            cur = conn.execute(
                "UPDATE profile_criteria SET relevance = ? WHERE profile_id = ?"
                " AND criterion_id = ?",
                (relevance, profile_id, criterion_id),
            )
            if cur.rowcount == 0:
                raise StoreError(
                    "That criterion is not on this profile, so its relevance here "
                    "cannot be changed. Add it first.")

    def copy_criteria_to_profile(
        self, account_id: int, source_profile_id: int, target_profile_id: int,
        criterion_ids: Sequence[int] | None = None,
    ) -> list[int]:
        """Copy criteria and their settings from one profile to another.

        A **copy**, deliberately — the settings are duplicated and the provenance is
        recorded, but the two profiles are then independent. Editing the target must never
        reach back into the source. They are separate saved configurations even where they
        share a standard.
        """
        if source_profile_id == target_profile_id:
            raise StoreError("Cannot copy a profile's criteria into itself.")
        with self.read() as conn:
            # Both ends, so a copy can never pull another account's configuration in.
            self._assert_owns(conn, "profiles", source_profile_id, account_id)
            self._assert_owns(conn, "profiles", target_profile_id, account_id)
            sql = "SELECT * FROM profile_criteria WHERE profile_id = ?"
            args: list[Any] = [source_profile_id]
            if criterion_ids:
                sql += f" AND criterion_id IN ({','.join('?' * len(criterion_ids))})"
                args.extend(criterion_ids)
            rows = [dict(r) for r in conn.execute(sql, args)]

        created: list[int] = []
        for row in rows:
            try:
                created.append(self.add_criterion_to_profile(
                    account_id, target_profile_id, row["criterion_id"],
                    tier=row["tier"], relevance=row["relevance"],
                    copied_from_profile_id=source_profile_id,
                ))
            except sqlite3.IntegrityError:
                continue  # already in the target; leave the target's own setting alone
        return created

    def list_profile_criteria(self, account_id: int, profile_id: int, *,
                              include_na: bool = True):
        with self.read() as conn:
            self._assert_owns(conn, "profiles", profile_id, account_id)
        sql = ("SELECT pc.*, c.value, c.desired_behavior, c.why_it_matters,"
               " c.examples_json, c.lineage_id, c.version, c.status"
               " FROM profile_criteria pc JOIN criteria c ON c.id = pc.criterion_id"
               " WHERE pc.profile_id = ? AND c.status = 'active'")
        if not include_na:
            sql += " AND pc.relevance = 'relevant'"
        sql += (" ORDER BY CASE pc.tier WHEN 'mandatory' THEN 0 WHEN 'preferred' THEN 1"
                " ELSE 2 END, pc.sort_order, c.value")
        with self.read() as conn:
            out = []
            for r in conn.execute(sql, (profile_id,)):
                d = dict(r)
                d["examples"] = json.loads(d.pop("examples_json") or "[]")
                d["criterion_id"] = d["criterion_id"]
                out.append(d)
            return out

    def revise_criterion(self, account_id: int, criterion_id: int, *,
                         revision_note: str | None = None, **changes: Any) -> int:
        """Write a NEW version and supersede the old row. Never an UPDATE of the text.

        The old version keeps its own ``created_at`` and gains ``superseded_at``, so the My
        Progress screen can show when a standard changed and what it changed from. That
        history is the point; see the module docstring.
        """
        allowed = {"value", "desired_behavior", "why_it_matters", "examples"}
        unknown = set(changes) - allowed
        if unknown:
            raise StoreError(f"Cannot revise unknown field(s): {', '.join(sorted(unknown))}")

        with self.write() as conn:
            old = conn.execute(
                "SELECT * FROM criteria WHERE id = ? AND account_id = ?",
                (criterion_id, account_id),
            ).fetchone()
            if old is None:
                raise NotOwned(f"No criterion {criterion_id} for this account.")
            if old["status"] == "superseded":
                raise StoreError(
                    f"Criterion {criterion_id} is already superseded; revise its current "
                    "version instead."
                )

            merged = {
                "value": changes.get("value", old["value"]),
                "desired_behavior": changes.get("desired_behavior", old["desired_behavior"]),
                "why_it_matters": changes.get("why_it_matters", old["why_it_matters"]),
                "examples_json": json.dumps(list(changes["examples"]))
                if "examples" in changes else old["examples_json"],
            }
            cur = conn.execute(
                "INSERT INTO criteria (account_id, lineage_id, version, value,"
                " desired_behavior, why_it_matters, examples_json,"
                " status, revision_note, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
                (
                    old["account_id"], old["lineage_id"],
                    old["version"] + 1, merged["value"], merged["desired_behavior"],
                    merged["why_it_matters"],
                    merged["examples_json"], revision_note, _now(),
                ),
            )
            conn.execute(
                "UPDATE criteria SET status = 'superseded', superseded_at = ? WHERE id = ?",
                (_now(), criterion_id),
            )
            return int(cur.lastrowid)

    def retire_criterion(self, account_id: int, criterion_id: int,
                         note: str | None = None) -> None:
        with self.write() as conn:
            cur = conn.execute(
                "UPDATE criteria SET status = 'retired', superseded_at = ?,"
                " revision_note = COALESCE(?, revision_note)"
                " WHERE id = ? AND account_id = ?",
                (_now(), note, criterion_id, account_id),
            )
            if cur.rowcount == 0:
                raise NotOwned(f"No criterion {criterion_id} for this account.")

    def list_criteria(self, account_id: int, *, status: str = "active"):
        """The Master Criteria Library. No tiers here — those belong to profiles."""
        sql = "SELECT * FROM criteria WHERE account_id = ?"
        args: list[Any] = [account_id]
        if status != "all":
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY value, version"
        with self.read() as conn:
            return [self._criterion_row(r) for r in conn.execute(sql, args)]

    def criterion_history(self, account_id: int, lineage_id: str):
        """Every version of one criterion, oldest first — the 'changing priorities' view."""
        with self.read() as conn:
            return [
                self._criterion_row(r)
                for r in conn.execute(
                    "SELECT * FROM criteria WHERE account_id = ? AND lineage_id = ?"
                    " ORDER BY version",
                    (account_id, lineage_id),
                )
            ]

    @staticmethod
    def _criterion_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["examples"] = json.loads(d.pop("examples_json") or "[]")
        return d

    # ----------------------------------------------------------------- assessments

    def set_assessment(
        self, account_id: int, profile_id: int, criterion_id: int, person_id: int,
        status: str, *, note: str | None = None, origin: str = "user",
        explanation: str | None = None,
    ) -> int:
        """Set Pass / Unknown / Fail / Not Applicable. **Only the user reaches this.**

        No agent code path writes here. An agent that wants to change a status calls
        ``propose_assessment`` and waits. That separation is why this is enforceable
        rather than merely promised.

        The status is scoped to a profile: the same person under Husband KRYteria and
        under One Night Stand KRYteria has two independent answers.

        Every transition is appended to ``assessment_history`` — previous status, new
        status, origin, explanation — because "how my reading changed as evidence arrived"
        is only answerable if the transitions survive.
        """
        if status not in ASSESSMENT_STATUSES:
            raise StoreError(
                f"status must be one of {ASSESSMENT_STATUSES}, got {status!r}"
            )
        if origin not in ("user", "user_accepted_proposal", "user_edited_proposal",
                          "system_initial"):
            raise StoreError(f"Unknown origin: {origin!r}")
        previous = self.get_assessment(account_id, profile_id, criterion_id, person_id)
        with self.write() as conn:
            conn.execute(
                "INSERT INTO assessments (account_id, profile_id, criterion_id, person_id,"
                " status, note, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(profile_id, criterion_id, person_id) DO UPDATE SET"
                "  status = excluded.status, note = excluded.note,"
                "  updated_at = excluded.updated_at",
                (account_id, profile_id, criterion_id, person_id, status, note, _now()),
            )
            row = conn.execute(
                "SELECT id FROM assessments WHERE profile_id = ? AND criterion_id = ?"
                " AND person_id = ?",
                (profile_id, criterion_id, person_id),
            ).fetchone()
            assessment_id = int(row["id"])
            conn.execute(
                "INSERT INTO assessment_history (assessment_id, previous_status,"
                " new_status, origin, explanation, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (assessment_id, previous, status, origin, explanation, _now()),
            )
            return assessment_id

    def get_assessment(self, account_id: int, profile_id: int, criterion_id: int,
                       person_id: int) -> str:
        """Unknown until somebody says otherwise.

        Note what this does NOT do: it never falls back to another profile's answer.
        A person unassessed under this profile is `unknown` here even if they passed the
        same criterion elsewhere.
        """
        with self.read() as conn:
            row = conn.execute(
                "SELECT status FROM assessments WHERE account_id = ? AND profile_id = ?"
                " AND criterion_id = ? AND person_id = ?",
                (account_id, profile_id, criterion_id, person_id),
            ).fetchone()
        return row["status"] if row else "unknown"

    def assessment_history(self, account_id: int, assessment_id: int):
        with self.read() as conn:
            self._assert_owns(conn, "assessments", assessment_id, account_id)
            return [
                dict(r) for r in conn.execute(
                    "SELECT * FROM assessment_history WHERE assessment_id = ?"
                    " ORDER BY created_at, id",
                    (assessment_id,),
                )
            ]

    def assessment_board(self, account_id: int, profile_id: int, person_id: int):
        """This profile's criteria with this person's status against each.

        Criteria the user marked ``not_applicable`` for the profile report that status
        rather than ``unknown`` — Not Applicable is a real answer, not missing evidence.
        """
        rows = self.list_profile_criteria(account_id, profile_id)
        for r in rows:
            if r["relevance"] == "not_applicable":
                r["assessment"] = "not_applicable"
            else:
                r["assessment"] = self.get_assessment(
                    account_id, profile_id, r["criterion_id"], person_id
                )
        return rows

    def propose_assessment(
        self, account_id: int, profile_id: int, criterion_id: int, person_id: int,
        proposed_status: str, rationale: str, *, run_id: int | None = None,
    ) -> int:
        """What an agent may do instead of changing a status: ask.

        The proposal is inert. Nothing in the app reads a pending proposal as though it
        were the status.
        """
        if proposed_status not in ASSESSMENT_STATUSES:
            raise StoreError(f"Unknown proposed status: {proposed_status!r}")
        if not (rationale or "").strip():
            raise StoreError(
                "A proposed status change must say why, in evidence terms. "
                "An unexplained proposal is a silent change with extra steps."
            )
        current = self.get_assessment(account_id, profile_id, criterion_id, person_id)
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO assessment_proposals (account_id, profile_id, criterion_id,"
                " person_id, current_status, proposed_status, rationale, run_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, profile_id, criterion_id, person_id, current,
                 proposed_status, rationale.strip(), run_id, _now()),
            )
            return int(cur.lastrowid)

    def list_pending_proposals(self, account_id: int):
        with self.read() as conn:
            return [
                dict(r) for r in conn.execute(
                    "SELECT ap.*, c.value AS criterion_value, p.alias AS person_alias"
                    " FROM assessment_proposals ap"
                    " JOIN criteria c ON c.id = ap.criterion_id"
                    " JOIN people p ON p.id = ap.person_id"
                    " WHERE ap.account_id = ? AND ap.resolution = 'pending'"
                    " ORDER BY ap.created_at",
                    (account_id,),
                )
            ]

    def resolve_proposal(
        self, account_id: int, proposal_id: int, resolution: str,
        *, final_status: str | None = None,
    ) -> None:
        """The user accepts, rejects or edits. Only 'accepted'/'edited' touch the status."""
        if resolution not in ("accepted", "rejected", "edited"):
            raise StoreError(f"Unknown resolution: {resolution!r}")
        with self.read() as conn:
            row = conn.execute(
                "SELECT * FROM assessment_proposals WHERE id = ? AND account_id = ?",
                (proposal_id, account_id),
            ).fetchone()
        if row is None:
            raise StoreError(f"No proposal {proposal_id}")
        if row["resolution"] != "pending":
            raise StoreError(f"Proposal {proposal_id} is already {row['resolution']}")

        if resolution in ("accepted", "edited"):
            status = final_status if resolution == "edited" else row["proposed_status"]
            if status is None:
                raise StoreError("An edited proposal must name the status the user chose.")
            self.set_assessment(
                account_id, row["profile_id"], row["criterion_id"], row["person_id"],
                status,
                origin=("user_edited_proposal" if resolution == "edited"
                        else "user_accepted_proposal"),
                explanation=row["rationale"],
            )

        with self.write() as conn:
            conn.execute(
                "UPDATE assessment_proposals SET resolution = ?, resolved_at = ?"
                " WHERE id = ?",
                (resolution, _now(), proposal_id),
            )

    # ----------------------------------------------------------------- evidence links

    def link_evidence(
        self, account_id: int, *, entry_id: int, criterion_id: int, relation: str,
        profile_id: int | None = None,
        observation_id: int | None = None, person_id: int | None = None,
        rationale: str | None = None, source_level: str = "agent_hypothesis",
        research_ref: str | None = None, proposed_by: str = "agent",
        run_id: int | None = None,
    ) -> int:
        """Map one observation to one criterion, one of four ways.

        Agent-proposed links start ``pending``. The user accepts, rejects or edits them —
        the mapping is a suggestion, not a fact about their life.
        """
        if relation not in EVIDENCE_RELATIONS:
            raise StoreError(
                f"relation must be one of {EVIDENCE_RELATIONS}, got {relation!r}"
            )
        if source_level not in SOURCE_LEVELS:
            raise StoreError(f"Unknown source_level: {source_level!r}")
        if source_level in ("established_research", "research_informed"):
            # A citation must RESOLVE, not merely exist.
            #
            # Requiring a non-empty string only guaranteed the model wrote something, and
            # a model told to cite will always write something — plausible, specific, and
            # possibly invented. Requiring the ref to match a verified row makes
            # fabrication impossible rather than discouraged: the agent can only cite
            # what a human checked and put here.
            #
            # The cost is that the research layer is exactly as broad as the curated set.
            # For a product whose whole position is evidence over assumption, that is the
            # right trade.
            if not research_ref:
                raise StoreError(
                    "A research-backed link must cite a knowledge-base entry, so the "
                    "user can see why the behaviour was suggested."
                )
            citable = self.citable_refs()
            if research_ref not in citable:
                raise StoreError(
                    f"research_ref {research_ref!r} does not match a verified entry in "
                    f"the knowledge base. {len(citable)} entries are currently citable. "
                    "An unverifiable citation is worse than none — mark this "
                    "'agent_hypothesis' instead, which needs no citation and is honest."
                )
        resolution = "accepted" if proposed_by == "user" else "pending"
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO evidence_links (account_id, profile_id, observation_id,"
                " entry_id, criterion_id, person_id, relation, rationale, source_level,"
                " research_ref, proposed_by, resolution, run_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, profile_id, observation_id, entry_id, criterion_id,
                 person_id, relation, rationale, source_level, research_ref, proposed_by,
                 resolution, run_id, _now()),
            )
            return int(cur.lastrowid)

    def resolve_evidence_link(
        self, account_id: int, link_id: int, resolution: str,
        *, relation: str | None = None,
    ) -> None:
        if resolution not in ("accepted", "rejected", "edited"):
            raise StoreError(f"Unknown resolution: {resolution!r}")
        if resolution == "edited":
            if relation not in EVIDENCE_RELATIONS:
                raise StoreError("An edited link must name the relation the user chose.")
        with self.write() as conn:
            conn.execute(
                "UPDATE evidence_links SET resolution = ?, resolved_at = ?,"
                " relation = COALESCE(?, relation) WHERE id = ? AND account_id = ?",
                (resolution, _now(), relation, link_id, account_id),
            )

    def list_evidence_links(
        self, account_id: int, *, criterion_id: int | None = None,
        entry_id: int | None = None, resolution: str | None = None,
    ):
        sql = ("SELECT el.*, c.value AS criterion_value"
               " FROM evidence_links el JOIN criteria c ON c.id = el.criterion_id"
               " WHERE el.account_id = ?")
        args: list[Any] = [account_id]
        for col, val in (("criterion_id", criterion_id), ("entry_id", entry_id),
                         ("resolution", resolution)):
            if val is not None:
                sql += f" AND el.{col} = ?"
                args.append(val)
        sql += " ORDER BY el.created_at DESC"
        with self.read() as conn:
            return [dict(r) for r in conn.execute(sql, args)]

    # ----------------------------------------------------------------- checklist mode

    def save_checklist_items(
        self, account_id: int, criterion_id: int, items: Sequence[dict[str, Any]],
        *, profile_id: int | None = None, run_id: int | None = None,
    ) -> list[int]:
        """Direction A: a criterion turned into observable behavioural indicators."""
        ids: list[int] = []
        with self.write() as conn:
            for i, item in enumerate(items):
                text = (item.get("text") or "").strip()
                if not text:
                    continue
                level = item.get("source_level", "research_informed")
                if level not in SOURCE_LEVELS:
                    raise StoreError(f"Unknown source_level: {level!r}")
                ref = item.get("research_ref")
                if level in ("established_research", "research_informed"):
                    if not ref:
                        raise StoreError(
                            f"Indicator {text!r} claims a research basis but cites nothing."
                        )
                    # Same rule as evidence links: the citation must resolve to a
                    # verified entry, so a confident-sounding invented reference cannot
                    # reach a checklist the user will tick.
                    if ref not in self.citable_refs():
                        raise StoreError(
                            f"Indicator {text!r} cites {ref!r}, which is not a verified "
                            "knowledge-base entry. Use 'agent_hypothesis' instead — it "
                            "needs no citation and does not overstate what this is."
                        )
                polarity = item.get("polarity", "demonstrates")
                if polarity not in ("demonstrates", "contradicts"):
                    raise StoreError(f"Unknown polarity: {polarity!r}")
                cur = conn.execute(
                    "INSERT INTO checklist_items (account_id, criterion_id, profile_id,"
                    " text, polarity, source_level, research_ref, sort_order, run_id,"
                    " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (account_id, criterion_id, profile_id, text, polarity, level, ref, i,
                     run_id, _now()),
                )
                ids.append(int(cur.lastrowid))
        return ids

    def list_checklist(self, account_id: int, criterion_id: int,
                       *, profile_id: int | None = None, person_id: int | None = None):
        sql = ("SELECT * FROM checklist_items WHERE account_id = ? AND criterion_id = ?"
               " AND is_active = 1")
        args: list[Any] = [account_id, criterion_id]
        if profile_id is not None:
            sql += " AND (profile_id = ? OR profile_id IS NULL)"
            args.append(profile_id)
        sql += " ORDER BY sort_order, id"
        with self.read() as conn:
            rows = [dict(r) for r in conn.execute(sql, args)]
            if person_id is not None:
                for row in rows:
                    counts = conn.execute(
                        "SELECT state, COUNT(*) AS n FROM checklist_observations"
                        " WHERE checklist_item_id = ? AND person_id = ? GROUP BY state",
                        (row["id"], person_id),
                    ).fetchall()
                    by_state = {r["state"]: int(r["n"]) for r in counts}
                    row["times_observed"] = by_state.get("observed", 0)
                    row["times_contradicted"] = by_state.get("contradicted", 0)
                    row["no_opportunity"] = by_state.get("no_opportunity", 0)
            return rows

    def record_checklist_observation(
        self, account_id: int, checklist_item_id: int, *, person_id: int | None = None,
        entry_id: int | None = None, state: str = "observed", note: str | None = None,
        occurred_on: str | None = None,
    ) -> int:
        """Record what was seen against one indicator.

        Four states, because "I never had the chance to see this" is different from
        "I looked and it wasn't there" — collapsing them turns absence of evidence into
        evidence of absence.

        This records an *observation*. It does not, and must not, move the criterion's
        Pass/Unknown/Fail status — there is no code path from here to ``set_assessment``.
        Only the user sets Pass.
        """
        if state not in CHECKLIST_STATES:
            raise StoreError(f"state must be one of {CHECKLIST_STATES}, got {state!r}")
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO checklist_observations (account_id, checklist_item_id,"
                " person_id, entry_id, state, note, occurred_on, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, checklist_item_id, person_id, entry_id, state, note,
                 occurred_on or _today(), _now()),
            )
            return int(cur.lastrowid)

    # ----------------------------------------------------------------- interrogation

    def save_interrogation(
        self, account_id: int, *, entry_id: int, claim: str, gap_kind: str,
        question: str, claim_valence: str = "negative", materiality: str = "material",
        run_id: int | None = None,
    ) -> int:
        """A question about the claim, never about the user."""
        if claim_valence not in ("negative", "positive", "neutral"):
            raise StoreError(f"Unknown claim_valence: {claim_valence!r}")
        if materiality not in ("material", "optional"):
            raise StoreError(f"Unknown materiality: {materiality!r}")
        if gap_kind not in GAP_KINDS:
            raise StoreError(f"gap_kind must be one of {GAP_KINDS}, got {gap_kind!r}")
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO interrogations (account_id, entry_id, claim, claim_valence,"
                " gap_kind, question, materiality, asked_at, run_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, entry_id, claim.strip(), claim_valence, gap_kind,
                 question.strip(), materiality, _now(), run_id),
            )
            return int(cur.lastrowid)

    def answer_interrogation(self, account_id: int, interrogation_id: int,
                             answer: str | None) -> None:
        """The user may always decline. A declined question is not asked again."""
        column = "answered_at" if answer else "declined_at"
        with self.write() as conn:
            conn.execute(
                f"UPDATE interrogations SET answer = ?, {column} = ?"
                " WHERE id = ? AND account_id = ?",
                (answer, _now(), interrogation_id, account_id),
            )

    def list_interrogations(self, account_id: int, *, entry_id: int | None = None,
                            unanswered_only: bool = False):
        sql = "SELECT * FROM interrogations WHERE account_id = ?"
        args: list[Any] = [account_id]
        if entry_id is not None:
            sql += " AND entry_id = ?"
            args.append(entry_id)
        if unanswered_only:
            sql += " AND answered_at IS NULL AND declined_at IS NULL"
        sql += " ORDER BY materiality = 'optional', asked_at"
        with self.read() as conn:
            return [dict(r) for r in conn.execute(sql, args)]

    # ----------------------------------------------------------------- research layer

    def add_research_note(
        self, *, ref: str, area: str, finding: str, citation: str, caveat: str,
        concept: str | None = None, attribution: str | None = None,
        citation_confidence: str | None = None,
        citation_checked_against: str | None = None,
        source_url: str | None = None, do_not: Sequence[str] = (),
        indicator_hints: Sequence[str] = (), safety_adjacent: bool = False,
        verified_at: str | None = None, verified_by: str | None = None,
    ) -> int:
        """Add a finding to the knowledge base.

        ``caveat`` is required, not optional. A finding without a statement of what it
        cannot tell you about one person is exactly the shape that gets misused, and this
        product's whole position is that research informs noticing and never decides.

        A note is **pending** unless ``verified_at`` is supplied, and a pending note is
        invisible to the agents.
        """
        if not (citation or "").strip():
            raise StoreError("A research note without a citation is just an assertion.")
        if not (caveat or "").strip():
            raise StoreError(
                f"Research note {ref!r} has no caveat. Every finding must say what it "
                "cannot tell you about one person."
            )
        if verified_at:
            # A pack file cannot mark its own work verified against a source KRYteria
            # would not cite. Same gate as verify_research_note, so there is no second
            # door into the citable set.
            from .sources import UnacceptableSource, check_source

            if not (source_url or "").strip():
                raise StoreError(
                    f"Research note {ref!r} is marked verified but records no "
                    "source_url. Verification means somebody opened something."
                )
            try:
                check_source(source_url)
            except UnacceptableSource as e:
                raise StoreError(f"Research note {ref!r}: {e}") from e
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO research_notes (ref, area, concept, finding, attribution,"
                " citation, citation_confidence, citation_checked_against, source_url,"
                " caveat, do_not_json, indicator_hints_json,"
                " safety_adjacent, verified_at, verified_by, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ref, area, concept, finding.strip(), attribution, citation.strip(),
                 citation_confidence, citation_checked_against,
                 source_url, caveat.strip(), json.dumps(list(do_not)),
                 json.dumps(list(indicator_hints)), int(safety_adjacent),
                 verified_at, verified_by, _now()),
            )
            return int(cur.lastrowid)

    def list_research_notes(self, area: str | None = None, *,
                            include_pending: bool = False,
                            include_safety_adjacent: bool = False):
        """Findings the agents may use.

        **Unverified notes are filtered out by default.** ``include_pending=True`` exists
        for the verification UI and for tests, never for an agent.

        Safety-adjacent notes are also withheld unless asked for: they may inform how the
        safety layer describes a behaviour and nothing else, so the Criteria and Evidence
        agents must not see them at all.
        """
        sql = "SELECT * FROM research_notes"
        clauses: list[str] = []
        args: list[Any] = []
        if area:
            clauses.append("area = ?")
            args.append(area)
        if not include_pending:
            clauses.append("verified_at IS NOT NULL")
        if not include_safety_adjacent:
            clauses.append("safety_adjacent = 0")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY area, ref"
        with self.read() as conn:
            rows = [dict(r) for r in conn.execute(sql, args)]
        for r in rows:
            r["do_not"] = json.loads(r.pop("do_not_json") or "[]")
            r["indicator_hints"] = json.loads(r.pop("indicator_hints_json") or "[]")
        return rows

    def citable_refs(self) -> set[str]:
        """Exactly what a research-backed claim may cite: verified refs, nothing else."""
        with self.read() as conn:
            return {
                r["ref"] for r in conn.execute(
                    "SELECT ref FROM research_notes WHERE verified_at IS NOT NULL"
                )
            }

    def verify_research_note(self, ref: str, *, source_url: str, verified_by: str) -> None:
        """Promote a pending note. Only a human does this, and it records what they opened.

        The URL must pass ``sources.check_source``: a .gov or .edu domain, a scholarly
        publisher, a permanent identifier, or a library catalogue. A well-meaning
        verification against a wellness blog is refused rather than quietly admitted.
        """
        from .sources import UnacceptableSource, check_source

        try:
            check_source(source_url)
        except UnacceptableSource as e:
            raise StoreError(str(e)) from e
        with self.write() as conn:
            cur = conn.execute(
                "UPDATE research_notes SET verified_at = ?, verified_by = ?,"
                " source_url = ? WHERE ref = ?",
                (_now(), verified_by, source_url.strip(), ref),
            )
            if cur.rowcount == 0:
                raise StoreError(f"No research note {ref!r}.")

    def load_research_pack(self, path: Path | str) -> dict[str, int]:
        """Load ``data/research/*.json``. Everything arrives pending unless the file
        says otherwise, and the file is not trusted to mark its own work verified
        without a source URL."""
        blob = json.loads(Path(path).read_text(encoding="utf-8"))
        added, refreshed, kept = 0, 0, 0
        rows = self.list_research_notes(include_pending=True, include_safety_adjacent=True)
        pending = {r["ref"] for r in rows if not r["verified_at"]}
        verified_already = {r["ref"] for r in rows if r["verified_at"]}

        for note in blob.get("notes", []):
            ref = note["id"]
            if ref in verified_already:
                # Never silently overwrite something a human signed off on. Re-verify
                # deliberately instead: an edit to the file must not change the meaning
                # of an approval that was given for different wording.
                kept += 1
                continue
            if ref in pending:
                # Safe to refresh: nobody has approved this yet, so there is no judgement
                # to preserve. This is how a corrected citation reaches the database.
                with self.write() as conn:
                    conn.execute("DELETE FROM research_notes WHERE ref = ?", (ref,))
                refreshed += 1
            verified = note.get("verification_status") == "verified"
            self.add_research_note(
                ref=note["id"], area=note["area"], concept=note.get("concept"),
                finding=note["finding"], attribution=note.get("attribution"),
                citation=note["citation"],
                citation_confidence=note.get("citation_confidence"),
                citation_checked_against=note.get("citation_checked_against"),
                source_url=note.get("source_url"),
                caveat=note["caveat"], do_not=note.get("do_not", []),
                indicator_hints=note.get("indicator_hints", []),
                safety_adjacent=bool(note.get("safety_adjacent")),
                verified_at=note.get("verified_at") if verified else None,
                verified_by=note.get("verified_by") if verified else None,
            )
            added += 1
        return {"added": added - refreshed, "refreshed": refreshed,
                "kept_verified": kept, "citable": len(self.citable_refs())}

    # ----------------------------------------------------------------- entries

    def create_entry(
        self,
        account_id: int,
        domain_id: int,
        *,
        occurred_on: str | None = None,
        entry_mode: str = "free",
        body: str | None = None,
        what_happened: str | None = None,
        what_expected: str | None = None,
        how_it_affected: str | None = None,
        witness: str = "firsthand",
        people: Sequence[str] = (),
        person_id: int | None = None,
        criterion_ids: Sequence[int] = (),
    ) -> int:
        """Free text and structured fields are both first-class; neither is a fallback."""
        if entry_mode not in ("free", "structured"):
            raise StoreError(f"Unknown entry_mode: {entry_mode}")
        if entry_mode == "free" and not (body or "").strip():
            raise StoreError("A free entry needs something written in it.")
        if entry_mode == "structured" and not any(
            (what_happened, what_expected, how_it_affected)
        ):
            raise StoreError("A structured entry needs at least one field filled in.")

        person_ids = [self.upsert_person(account_id, a, domain_id=domain_id)
                      for a in people if a and a.strip()]
        # An already-known person, chosen from the picker rather than typed. Without
        # this the entry is never linked to them, and "what recurs with this person"
        # silently has nothing to work from.
        if person_id is not None:
            with self.read() as conn:
                self._assert_owns(conn, "people", person_id, account_id)
            person_ids.append(person_id)

        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO entries (account_id, domain_id, occurred_on, entry_mode, body,"
                " what_happened, what_expected, how_it_affected, witness, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id, domain_id, occurred_on or _today(), entry_mode, body,
                    what_happened, what_expected, how_it_affected, witness, _now(),
                ),
            )
            entry_id = int(cur.lastrowid)
            for pid in person_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO entry_people (entry_id, person_id) VALUES (?, ?)",
                    (entry_id, pid),
                )
            for cid in criterion_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO entry_criteria (entry_id, criterion_id, linked_by)"
                    " VALUES (?, ?, 'user')",
                    (entry_id, cid),
                )
            return entry_id

    def list_entries(
        self, account_id: int, *, domain_id: int | None = None, limit: int = 50,
        since: str | None = None, search: str | None = None,
    ):
        sql = "SELECT * FROM entries WHERE account_id = ? AND deleted_at IS NULL"
        args: list[Any] = [account_id]
        if domain_id is not None:
            sql += " AND domain_id = ?"
            args.append(domain_id)
        if since:
            sql += " AND occurred_on >= ?"
            args.append(since)
        if search:
            sql += (" AND (COALESCE(body,'') LIKE ? OR COALESCE(what_happened,'') LIKE ?"
                    " OR COALESCE(what_expected,'') LIKE ?"
                    " OR COALESCE(how_it_affected,'') LIKE ?)")
            args.extend([f"%{search}%"] * 4)
        sql += " ORDER BY occurred_on DESC, id DESC LIMIT ?"
        args.append(limit)
        with self.read() as conn:
            return [dict(r) for r in conn.execute(sql, args)]

    def get_entry(self, account_id: int, entry_id: int) -> dict[str, Any] | None:
        with self.read() as conn:
            row = conn.execute(
                "SELECT * FROM entries WHERE id = ? AND account_id = ? AND deleted_at IS NULL",
                (entry_id, account_id),
            ).fetchone()
            if row is None:
                return None
            entry = dict(row)
            entry["people"] = [
                r["alias"] for r in conn.execute(
                    "SELECT p.alias FROM entry_people ep JOIN people p ON p.id = ep.person_id"
                    " WHERE ep.entry_id = ?",
                    (entry_id,),
                )
            ]
            return entry

    def delete_entry(self, account_id: int, entry_id: int) -> None:
        with self.write() as conn:
            conn.execute(
                "UPDATE entries SET deleted_at = ? WHERE id = ? AND account_id = ?",
                (_now(), entry_id, account_id),
            )

    # ----------------------------------------------------------------- retention

    def apply_retention(self, account_id: int, entry_id: int,
                        retention: str | None = None) -> dict[str, Any]:
        """Erase what the user did not ask KRYteria to keep.

        Three outcomes:

          ``keep_all``       the narrative stays, with everything derived from it.
          ``analysis_only``  the narrative is erased; observations, mappings and
                             assessments survive. Somebody can keep the fact that they
                             noticed a pattern without keeping the 1 a.m. account of it.
          ``discard``        the narrative AND everything derived from it go. Nothing is
                             left to reconstruct it from.

        The entry row survives an erasure as a dated placeholder rather than being
        deleted, so surviving evidence still has something to point at. ``body`` and the
        structured fields are overwritten with NULL — not blanked, not tombstoned with
        their length, not kept "just in case".

        ``discard`` deliberately removes the derived records too. An observation reading
        "She stayed rather than have another argument" is a near-quotation; keeping it
        after someone asked for the narrative to be discarded would honour the letter and
        break the promise.
        """
        if retention is None:
            account = self.get_account(account_id)
            retention = (account or {}).get("retention", "analysis_only")
        if retention not in RETENTION_MODES:
            raise StoreError(
                f"retention must be one of {RETENTION_MODES}, got {retention!r}")

        with self.write() as conn:
            self._assert_owns(conn, "entries", entry_id, account_id)
            conn.execute("UPDATE entries SET retention = ? WHERE id = ?",
                         (retention, entry_id))

            if retention == "keep_all":
                return {"retention": retention, "original_erased": False,
                        "derived_removed": 0}

            removed = 0
            if retention == "discard":
                for table in ("observations", "evidence_links", "interrogations",
                              "entry_themes"):
                    cur = conn.execute(
                        f"DELETE FROM {table} WHERE entry_id = ? AND account_id = ?",
                        (entry_id, account_id),
                    )
                    removed += cur.rowcount
                conn.execute("DELETE FROM pattern_evidence WHERE entry_id = ?",
                             (entry_id,))
                conn.execute(
                    "DELETE FROM reconciliations WHERE entry_id = ? AND account_id = ?",
                    (entry_id, account_id),
                )

            conn.execute(
                "UPDATE entries SET body = NULL, what_happened = NULL,"
                " what_expected = NULL, how_it_affected = NULL, original_erased_at = ?"
                " WHERE id = ?",
                (_now(), entry_id),
            )
            return {"retention": retention, "original_erased": True,
                    "derived_removed": removed}

    def erase_originals(self, account_id: int, *, older_than: str | None = None) -> int:
        """Erase the narrative from every entry whose retention says not to keep it.

        A sweep, for a user who changes their default and wants it applied to what they
        already wrote, and as the backstop if an erasure was ever missed at write time.
        """
        with self.read() as conn:
            rows = [
                dict(r) for r in conn.execute(
                    "SELECT id, retention FROM entries WHERE account_id = ?"
                    " AND retention != 'keep_all' AND original_erased_at IS NULL"
                    + (" AND created_at < ?" if older_than else ""),
                    (account_id, older_than) if older_than else (account_id,),
                )
            ]
        for row in rows:
            self.apply_retention(account_id, row["id"], row["retention"])
        return len(rows)

    def retention_report(self, account_id: int) -> dict[str, Any]:
        """What is actually being kept, in the user's own terms.

        Exists so the Transparency principle is answerable from the data rather than
        from a paragraph somebody wrote once and never checked again.
        """
        with self.read() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM entries WHERE account_id = ?"
                " AND deleted_at IS NULL", (account_id,)
            ).fetchone()["n"]
            with_text = conn.execute(
                "SELECT COUNT(*) AS n FROM entries WHERE account_id = ?"
                " AND deleted_at IS NULL AND body IS NOT NULL", (account_id,)
            ).fetchone()["n"]
            erased = conn.execute(
                "SELECT COUNT(*) AS n FROM entries WHERE account_id = ?"
                " AND original_erased_at IS NOT NULL", (account_id,)
            ).fetchone()["n"]
            observations = conn.execute(
                "SELECT COUNT(*) AS n FROM observations WHERE account_id = ?",
                (account_id,)
            ).fetchone()["n"]
        account = self.get_account(account_id) or {}
        return {
            "default_retention": account.get("retention"),
            "entries": total,
            "originals_still_stored": with_text,
            "originals_erased": erased,
            "observations_kept": observations,
            "note": (
                "Erasing an original overwrites the text with NULL. The entry row stays "
                "as a dated placeholder so surviving observations still have something "
                "to point at."
            ),
        }

    # ----------------------------------------------------------------- observations

    # ------------------------------------------------------------- themes

    def save_themes(self, account_id: int, entry_id: int, theme_ids: Sequence[str],
                    *, run_id: int | None = None) -> list[str]:
        """Record what an entry was about. Ids only — the labels live in the vocabulary.

        Validated against ``data/themes.json`` here rather than trusted, for the same
        reason ``kind`` is validated in ``save_observations``: a vocabulary that accepts
        whatever arrives is not a vocabulary, and "this keeps coming up" computed over
        invented labels is worse than no answer.
        """
        from .themes import validate

        if not theme_ids:
            return []
        valid = validate(list(theme_ids))
        with self.write() as conn:
            self._assert_owns(conn, "entries", entry_id, account_id)
            for theme_id in valid:
                conn.execute(
                    "INSERT OR IGNORE INTO entry_themes"
                    " (account_id, entry_id, theme_id, run_id, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (account_id, entry_id, theme_id, run_id, _now()),
                )
        return valid

    def list_entry_themes(self, account_id: int, entry_id: int) -> list[str]:
        with self.read() as conn:
            self._assert_owns(conn, "entries", entry_id, account_id)
            return [r["theme_id"] for r in conn.execute(
                "SELECT theme_id FROM entry_themes WHERE account_id = ? AND entry_id = ?"
                " ORDER BY id", (account_id, entry_id),
            )]

    def theme_trends(self, account_id: int, *, person_id: int | None = None,
                     limit_entries: int = 200) -> list[dict[str, Any]]:
        """How often each theme has come up, and when it last did.

        This is the whole reason themes are stored rather than merely recognised. A
        person who writes about *comfort expressing needs* in nine entries out of twelve
        is being shown something about themselves that no single entry contains — and
        crucially, something they may never have created a criterion for.

        Counts and dates only. No score, no trend arrow, no "your intimacy is
        declining": the dashboard counts and compares, it does not rate.
        """
        sql = [
            "SELECT t.theme_id, COUNT(*) AS entries,",
            "       MIN(e.occurred_on) AS first_seen, MAX(e.occurred_on) AS last_seen",
            "  FROM entry_themes t JOIN entries e ON e.id = t.entry_id",
            " WHERE t.account_id = ? AND e.deleted_at IS NULL",
        ]
        params: list[Any] = [account_id]
        if person_id is not None:
            # Entries reach people through `entry_people`, not a column: one entry can
            # involve more than one person, which is ordinary in a journal.
            sql.append(" AND EXISTS (SELECT 1 FROM entry_people ep"
                       "             WHERE ep.entry_id = e.id AND ep.person_id = ?)")
            params.append(person_id)
        sql.append(" GROUP BY t.theme_id ORDER BY entries DESC, last_seen DESC")
        with self.read() as conn:
            if person_id is not None:
                self._assert_owns(conn, "people", person_id, account_id)
            return [dict(r) for r in conn.execute("\n".join(sql), params)]

    def save_observations(
        self, account_id: int, entry_id: int, observations: Iterable[dict[str, Any]],
        *, run_id: int | None = None, attributed_to: str = "agent",
    ) -> list[int]:
        """Store the Evidence agent's structured read of one entry.

        ``kind`` is validated here rather than trusted. The five kinds are the firewall
        between what the user reported and what was made of it, and a tool that accepted
        an unknown or missing kind would quietly put everything on the same footing.
        """
        ids: list[int] = []
        with self.write() as conn:
            for obs in observations:
                kind = obs.get("kind")
                if kind not in OBSERVATION_KINDS:
                    raise StoreError(
                        f"Observation kind must be one of {OBSERVATION_KINDS}, got {kind!r}"
                    )
                text = (obs.get("text") or "").strip()
                if not text:
                    continue
                certainty = obs.get("certainty", "stated")
                if certainty not in ("stated", "inferred"):
                    raise StoreError(f"Unknown certainty: {certainty!r}")
                hedge = obs.get("hedge")
                # "Infer, but don't presume." A reading of the narrative is allowed —
                # the user should not have to name a behaviour before the app can help
                # them look at it — but it must be marked as a reading and offered back
                # for confirmation, never stated as something they said.
                if certainty == "inferred" and not (hedge or "").strip():
                    raise StoreError(
                        f"Inferred observation {text[:40]!r} carries no hedge. An "
                        "inference presented as a statement of fact is a presumption."
                    )
                if certainty == "stated" and attributed_to == "agent" and \
                        kind == "reported_event" and hedge:
                    raise StoreError(
                        "A stated reported_event must not be hedged; mark it inferred."
                    )
                cur = conn.execute(
                    "INSERT INTO observations (account_id, entry_id, kind, text,"
                    " attributed_to, certainty, hedge, criterion_id, run_id, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        account_id, entry_id, kind, text, attributed_to, certainty,
                        hedge, obs.get("criterion_id"), run_id, _now(),
                    ),
                )
                ids.append(int(cur.lastrowid))
        return ids

    def list_observations(self, account_id: int, *, entry_ids: Sequence[int] | None = None,
                          kinds: Sequence[str] | None = None, limit: int = 300):
        sql = "SELECT * FROM observations WHERE account_id = ?"
        args: list[Any] = [account_id]
        if entry_ids:
            sql += f" AND entry_id IN ({','.join('?' * len(entry_ids))})"
            args.extend(entry_ids)
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            args.extend(kinds)
        sql += " ORDER BY entry_id, id LIMIT ?"
        args.append(limit)
        with self.read() as conn:
            return [dict(r) for r in conn.execute(sql, args)]

    # ----------------------------------------------------------------- patterns

    def save_pattern(
        self,
        account_id: int,
        *,
        profile_id: int | None = None,
        domain_id: int | None = None,
        kind: str,
        statement: str,
        evidence: Sequence[dict[str, Any]],
        criterion_id: int | None = None,
        evidence_strength: str = "limited",
        gap_note: str | None = None,
        uncertainties: Sequence[str] = (),
        alternatives: Sequence[str] = (),
        run_id: int | None = None,
    ) -> dict[str, Any]:
        """Write a finding, with the entries that back it and the entries that don't.

        Rules applied here that cannot be talked out of by a model or a journal entry:

        * **No evidence, no pattern.** An empty ``evidence`` list raises. Even an
          ``insufficient`` finding needs the entries that were looked at — "I checked these
          three and they don't settle it" is honest; "I have a feeling" is not.
        * **Counts are counted, not reported.** ``support_count`` and ``contra_count`` come
          from the distinct entry ids actually supplied, so a model claiming five
          supporting entries while naming two gets a two.
        * **Counter-evidence is stored, not discarded.** Evidence rows carry a ``stance``.
        * **Thin evidence is downgraded**, below ``MIN_SUPPORT`` supporting entries.
        * **A confident finding must admit another reading.** ``moderate`` and ``strong``
          are refused without at least one alternative explanation.
        """
        if not evidence:
            raise StoreError(
                "A pattern must name the journal entries it rests on. "
                "Refusing to write a finding with no evidence."
            )
        if evidence_strength not in EVIDENCE_STRENGTHS:
            raise StoreError(
                f"evidence_strength must be one of {EVIDENCE_STRENGTHS}, "
                f"got {evidence_strength!r}. Qualitative only — never a score."
            )

        supporting, contradicting = set(), set()
        for e in evidence:
            if not e.get("entry_id"):
                continue
            stance = e.get("stance", "supports")
            if stance not in ("supports", "contradicts"):
                raise StoreError(f"Unknown evidence stance: {stance!r}")
            (contradicting if stance == "contradicts" else supporting).add(int(e["entry_id"]))
        if not (supporting or contradicting):
            raise StoreError("Evidence rows must carry an entry_id.")

        support_count, contra_count = len(supporting), len(contradicting)

        if (evidence_strength in STRENGTHS_REQUIRING_ALTERNATIVES
                and not [a for a in alternatives if (a or "").strip()]):
            raise StoreError(
                f"A '{evidence_strength}' finding must offer at least one alternative "
                "explanation. A finding that admits no other reading is a verdict, and "
                "KRYteria does not issue verdicts."
            )

        downgraded = False
        if support_count < MIN_SUPPORT and evidence_strength != "insufficient":
            evidence_strength = "insufficient"
            downgraded = True
            gap_note = gap_note or (
                f"Only {support_count} entr{'y' if support_count == 1 else 'ies'} support "
                f"this so far. KRYteria needs at least {MIN_SUPPORT} before calling "
                "something a pattern."
            )

        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO patterns (account_id, profile_id, domain_id, kind, statement,"
                " criterion_id, support_count, contra_count, evidence_strength, gap_note,"
                " uncertainties_json, alternatives_json, run_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id, profile_id, domain_id, kind, statement.strip(),
                    criterion_id,
                    support_count, contra_count, evidence_strength, gap_note,
                    json.dumps([u for u in uncertainties if (u or "").strip()]),
                    json.dumps([a for a in alternatives if (a or "").strip()]),
                    run_id, _now(),
                ),
            )
            pattern_id = int(cur.lastrowid)
            for e in evidence:
                if not e.get("entry_id"):
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO pattern_evidence (pattern_id, entry_id,"
                    " observation_id, stance) VALUES (?, ?, ?, ?)",
                    (
                        pattern_id, int(e["entry_id"]), e.get("observation_id"),
                        e.get("stance", "supports"),
                    ),
                )

        return {
            "pattern_id": pattern_id,
            "support_count": support_count,
            "contra_count": contra_count,
            "evidence_strength": evidence_strength,
            "downgraded": downgraded,
        }

    def list_patterns(self, account_id: int, *, profile_id: int | None = None,
                      domain_id: int | None = None, status: str = "open"):
        sql = "SELECT * FROM patterns WHERE account_id = ?"
        args: list[Any] = [account_id]
        if profile_id is not None:
            sql += " AND profile_id = ?"
            args.append(profile_id)
        if domain_id is not None:
            sql += " AND domain_id = ?"
            args.append(domain_id)
        if status != "all":
            sql += " AND status = ?"
            args.append(status)
        sql += (" ORDER BY evidence_strength = 'insufficient', support_count DESC,"
                " created_at DESC")
        with self.read() as conn:
            rows = [dict(r) for r in conn.execute(sql, args)]
            for row in rows:
                row["uncertainties"] = json.loads(row.pop("uncertainties_json") or "[]")
                row["alternatives"] = json.loads(row.pop("alternatives_json") or "[]")
                all_evidence = [
                    dict(r) for r in conn.execute(
                        "SELECT pe.entry_id, pe.observation_id, pe.stance, e.occurred_on,"
                        " COALESCE(o.text, e.body, e.what_happened) AS excerpt"
                        " FROM pattern_evidence pe"
                        " JOIN entries e ON e.id = pe.entry_id"
                        " LEFT JOIN observations o ON o.id = pe.observation_id"
                        " WHERE pe.pattern_id = ? ORDER BY e.occurred_on",
                        (row["id"],),
                    )
                ]
                # Surfaced separately so the UI cannot show one without the other.
                row["evidence"] = [e for e in all_evidence if e["stance"] == "supports"]
                row["counter_evidence"] = [
                    e for e in all_evidence if e["stance"] == "contradicts"
                ]
            return rows

    def set_pattern_status(self, account_id: int, pattern_id: int, status: str) -> None:
        if status not in ("open", "addressed", "dismissed"):
            raise StoreError(f"Unknown pattern status: {status}")
        with self.write() as conn:
            conn.execute(
                "UPDATE patterns SET status = ? WHERE id = ? AND account_id = ?",
                (status, pattern_id, account_id),
            )

    # ----------------------------------------------------------------- reflection

    def save_reflection(
        self, account_id: int, *, question: str, tone_mode: str,
        pattern_id: int | None = None, context: str | None = None,
        is_postponement_probe: bool = False, run_id: int | None = None,
    ) -> int:
        if tone_mode not in TONE_MODES:
            raise StoreError(f"Unknown tone mode: {tone_mode}")
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO reflections (account_id, pattern_id, question, context,"
                " tone_mode, is_postponement_probe, run_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id, pattern_id, question.strip(), context, tone_mode,
                    int(is_postponement_probe), run_id, _now(),
                ),
            )
            return int(cur.lastrowid)

    def record_decision(
        self, account_id: int, *, choice: str, reflection_id: int | None = None,
        pattern_id: int | None = None, criterion_id: int | None = None,
        action_text: str | None = None, revisit_on: str | None = None,
    ) -> int:
        if choice not in DECISION_CHOICES:
            raise StoreError(f"Unknown decision: {choice}")
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO decisions (account_id, reflection_id, pattern_id, criterion_id,"
                " choice, action_text, revisit_on, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id, reflection_id, pattern_id, criterion_id, choice,
                    action_text, revisit_on, _now(),
                ),
            )
            return int(cur.lastrowid)

    def count_postponements(
        self, account_id: int, *, criterion_id: int | None = None,
        pattern_id: int | None = None,
    ) -> int:
        """How many times this same concern has been put off.

        Drives the signature question. It counts; it never judges — the number changes
        which question the Reflection agent is allowed to ask and nothing else.
        """
        sql = ("SELECT COUNT(*) AS n FROM decisions WHERE account_id = ?"
               " AND choice = 'more_time'")
        args: list[Any] = [account_id]
        if criterion_id is not None:
            sql += " AND criterion_id = ?"
            args.append(criterion_id)
        if pattern_id is not None:
            sql += " AND pattern_id = ?"
            args.append(pattern_id)
        with self.read() as conn:
            return int(conn.execute(sql, args).fetchone()["n"])

    def should_probe_postponement(self, account_id: int, **kw: Any) -> bool:
        return self.count_postponements(account_id, **kw) >= POSTPONEMENT_PROBE_AT

    def list_decisions(self, account_id: int, *, limit: int = 100):
        with self.read() as conn:
            return [
                dict(r) for r in conn.execute(
                    "SELECT d.*, p.statement AS pattern_statement, c.value AS criterion_value"
                    " FROM decisions d"
                    " LEFT JOIN patterns p ON p.id = d.pattern_id"
                    " LEFT JOIN criteria c ON c.id = d.criterion_id"
                    " WHERE d.account_id = ? ORDER BY d.created_at DESC LIMIT ?",
                    (account_id, limit),
                )
            ]

    # ----------------------------------------------------------------- agent log

    def start_run(self, account_id: int, route: str) -> int:
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO agent_runs (account_id, route, status, started_at)"
                " VALUES (?, ?, 'running', ?)",
                (account_id, route, _now()),
            )
            return int(cur.lastrowid)

    def finish_run(self, account_id: int, run_id: int, status: str,
                   detail: str | None = None) -> None:
        with self.write() as conn:
            conn.execute(
                "UPDATE agent_runs SET status = ?, detail = ?, finished_at = ?"
                " WHERE id = ? AND account_id = ?",
                (status, detail, _now(), run_id, account_id),
            )

    def log_step(
        self, account_id: int, run_id: int, seq: int, agent: str, *,
        tool_calls: Sequence[Any] = (),
        model_name: str | None = None, input_tokens: int = 0,
        cached_input_tokens: int | None = None, output_tokens: int = 0,
        estimated_cost_usd: float = 0.0, actual_cost_usd: float | None = None,
        latency_ms: int = 0, ok: bool = True, is_simulated: bool = False,
        error_message: str | None = None, note: str | None = None,
    ) -> None:
        """Record one agent step.

        ``cached_input_tokens=None`` means the provider did not report it, and is stored as
        NULL rather than 0 — see the schema comment. ``tool_calls`` must carry tool names
        and argument keys only; **never pass raw journal text into this table.**
        """
        with self.write() as conn:
            self._assert_owns(conn, "agent_runs", run_id, account_id)
            conn.execute(
                "INSERT INTO agent_steps (run_id, seq, agent, model_name, tool_calls_json,"
                " input_tokens, cached_input_tokens, output_tokens, estimated_cost_usd,"
                " actual_cost_usd, latency_ms, ok, is_simulated, error_message, note,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, seq, agent, model_name, json.dumps(list(tool_calls)),
                    input_tokens, cached_input_tokens, output_tokens, estimated_cost_usd,
                    actual_cost_usd, latency_ms, int(ok), int(is_simulated),
                    error_message, note, _now(),
                ),
            )

    def get_run(self, account_id: int, run_id: int) -> dict[str, Any] | None:
        """The trace the app shows on screen — and the agent-design evidence the rubric
        asks for: one real run, step by step, with what each agent did."""
        with self.read() as conn:
            run = conn.execute(
                "SELECT * FROM agent_runs WHERE id = ? AND account_id = ?",
                (run_id, account_id),
            ).fetchone()
            if run is None:
                return None
            out = dict(run)
            out["steps"] = [
                {**dict(r), "tool_calls": json.loads(r["tool_calls_json"])}
                for r in conn.execute(
                    "SELECT * FROM agent_steps WHERE run_id = ? ORDER BY seq", (run_id,)
                )
            ]
            billable = [s for s in out["steps"] if not s["is_simulated"]]
            out["input_tokens"] = sum(s["input_tokens"] for s in billable)
            out["output_tokens"] = sum(s["output_tokens"] for s in billable)
            # None, not 0, when no step reported a cached count — "we don't know" and
            # "the cache was cold" are different facts and the report must not merge them.
            reported = [s["cached_input_tokens"] for s in billable
                        if s["cached_input_tokens"] is not None]
            out["cached_input_tokens"] = sum(reported) if reported else None
            out["cached_tokens_reported"] = bool(reported)
            out["cost_usd"] = round(
                sum(s["actual_cost_usd"] if s["actual_cost_usd"] is not None
                    else s["estimated_cost_usd"] for s in billable), 6
            )
            out["cost_is_estimated"] = any(s["actual_cost_usd"] is None for s in billable)
            out["simulated_steps"] = len(out["steps"]) - len(billable)
            return out

    # ----------------------------------------------------------------- safety

    def log_safety_event(
        self, *, trigger: str, action: str, account_id: int | None = None,
        entry_id: int | None = None, run_id: int | None = None,
        category: str | None = None, concern_level: str = "potential",
        detail: str | None = None,
    ) -> int:
        """Record a safety concern. Deliberately takes no ``profile_id``.

        The safety layer runs in every context and is never gated on the user having
        listed safety as a criterion.
        """
        if concern_level not in CONCERN_LEVELS:
            raise StoreError(
                f"concern_level must be one of {CONCERN_LEVELS}, got {concern_level!r}"
            )
        if category is not None and category not in SAFETY_CATEGORIES:
            raise StoreError(f"Unknown safety category: {category!r}")
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO safety_events (account_id, entry_id, run_id, trigger,"
                " category, concern_level, action, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, entry_id, run_id, trigger, category, concern_level, action,
                 detail, _now()),
            )
            return int(cur.lastrowid)

    # ------------------------------------------------- support without coercion

    def list_resources(self, *, region: str | None = None, category: str | None = None,
                       kind: str | None = None, include_global: bool = True):
        """The curated directory. If it is not here, there is nothing to offer.

        The agent must never invent a phone number, a service, or an availability claim.
        An empty result means "I don't have a resource for that", which is a truthful
        thing to say and an invented hotline is not.

        ``region`` is an ISO 3166-1 alpha-2 code, or None for somebody who has not said
        where they are. **The default is no longer "US".** It was, and that meant a user
        in Osaka reaching for help got a number that does not work there — which is not
        a smaller failure than inventing one, it is the same failure with a real number
        attached. Emergency services differ: 999, 112, 000, 119. Getting this wrong
        during a crisis is the most expensive mistake this directory can make.

        ``GLOBAL`` rows are included by default: services that genuinely operate
        everywhere, which is a small set and must stay small.
        """
        regions = [r for r in (region, "GLOBAL" if include_global else None) if r]
        if not regions:
            # Nobody has said where they are and global rows were excluded. Honest empty.
            return []
        sql = ("SELECT * FROM resources WHERE is_active = 1 AND region IN ("
               + ",".join("?" * len(regions)) + ")")
        args: list[Any] = list(regions)
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        # A country-specific row outranks a global one: if somebody has told us where
        # they are, the local service is the better answer.
        sql += (" ORDER BY kind = 'emergency' DESC, region = 'GLOBAL' ASC, name")
        with self.read() as conn:
            rows = [dict(r) for r in conn.execute(sql, args)]
        for r in rows:
            r["categories"] = json.loads(r["categories"] or "[]")
        if category:
            rows = [r for r in rows if not r["categories"] or category in r["categories"]]
        return rows

    def should_offer_resources(self, account_id: int, concern_level: str) -> bool:
        """Whether to raise resources *unprompted* right now.

        Three things are true at once here, and the order matters:

        1. **Immediate danger always surfaces emergency options.** No preference and no
           previous decline suppresses that. Declining resources turns off unsolicited
           offering, not the safety layer.
        2. **A declined offer is respected.** If the user has said no at this level or
           below, the agent does not keep raising it. Being told "support is available"
           for the fourth time is its own harm — it teaches somebody that telling the app
           something hard makes it stop being able to talk to them.
        3. **The user's stated preference is honoured** for everything below immediate
           danger.

        Returns False freely. The agent can still *answer* — this governs only whether it
        volunteers resources.
        """
        if concern_level not in CONCERN_LEVELS:
            raise StoreError(f"Unknown concern level: {concern_level!r}")

        # 1. Immediate danger is never suppressed.
        if concern_level == "immediate_danger":
            return True

        account = self.get_account(account_id) or {}
        preference = account.get("resource_offering", "proactive")
        if preference in ("on_request", "suppressed"):
            return False

        # 2. Has the user already declined at this level or a more serious one?
        rank = CONCERN_LEVELS.index(concern_level)
        with self.read() as conn:
            declines = conn.execute(
                "SELECT concern_level FROM resource_offers WHERE account_id = ?"
                " AND response = 'declined'",
                (account_id,),
            ).fetchall()
        for row in declines:
            if CONCERN_LEVELS.index(row["concern_level"]) >= rank:
                return False
        return True

    def record_resource_offer(
        self, account_id: int, resource_ids: Sequence[int], concern_level: str,
        *, safety_event_id: int | None = None,
    ) -> int:
        if concern_level not in CONCERN_LEVELS:
            raise StoreError(f"Unknown concern level: {concern_level!r}")
        with self.write() as conn:
            cur = conn.execute(
                "INSERT INTO resource_offers (account_id, safety_event_id, resource_ids,"
                " concern_level, created_at) VALUES (?, ?, ?, ?, ?)",
                (account_id, safety_event_id, json.dumps(list(resource_ids)),
                 concern_level, _now()),
            )
            return int(cur.lastrowid)

    def respond_to_offer(self, account_id: int, offer_id: int, response: str) -> None:
        """The user accepts, declines, or ignores. A decline is honoured, not argued with."""
        if response not in ("accepted", "declined", "ignored"):
            raise StoreError(f"Unknown response: {response!r}")
        with self.write() as conn:
            conn.execute(
                "UPDATE resource_offers SET response = ?, responded_at = ?"
                " WHERE id = ? AND account_id = ?",
                (response, _now(), offer_id, account_id),
            )

    def seed_resources(self, entries: Sequence[dict[str, Any]]) -> list[int]:
        """Load the curated directory. Every row needs a verification date."""
        ids: list[int] = []
        with self.write() as conn:
            for r in entries:
                if not r.get("verified_at"):
                    raise StoreError(
                        f"Resource {r.get('name')!r} has no verified_at. An unverified "
                        "hotline number is worse than none."
                    )
                if not (r.get("phone") or r.get("url") or r.get("text_line")):
                    raise StoreError(
                        f"Resource {r.get('name')!r} has no way to reach it."
                    )
                if not r.get("region"):
                    raise StoreError(
                        f"Resource {r.get('name')!r} declares no region. This used to "
                        "default to 'US', which silently filed every international "
                        "service under the wrong country — and a number that does not "
                        "work where somebody is standing is no better than an invented "
                        "one. Use an ISO 3166-1 alpha-2 code, or 'GLOBAL' for a service "
                        "that genuinely operates everywhere."
                    )
                cur = conn.execute(
                    "INSERT INTO resources (region, name, kind, categories, phone,"
                    " text_line, url, hours, note, verified_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (r["region"].strip().upper(), r["name"], r["kind"],
                     json.dumps(r.get("categories", [])), r.get("phone"),
                     r.get("text_line"), r.get("url"), r.get("hours"), r.get("note"),
                     r["verified_at"]),
                )
                ids.append(int(cur.lastrowid))
        return ids

    def list_safety_events(self, account_id: int | None = None, limit: int = 100):
        sql = "SELECT * FROM safety_events"
        args: list[Any] = []
        if account_id is not None:
            sql += " WHERE account_id = ?"
            args.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self.read() as conn:
            return [dict(r) for r in conn.execute(sql, args)]

    # ----------------------------------------------------------------- usage + budget

    def add_usage(
        self, account_id: int, *, calls: int = 1, input_tokens: int = 0,
        output_tokens: int = 0, cost_usd: float = 0.0,
    ) -> None:
        with self.write() as conn:
            conn.execute(
                "INSERT INTO usage_daily (account_id, day, calls, input_tokens,"
                " output_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(account_id, day) DO UPDATE SET"
                "  calls = calls + excluded.calls,"
                "  input_tokens = input_tokens + excluded.input_tokens,"
                "  output_tokens = output_tokens + excluded.output_tokens,"
                "  cost_usd = cost_usd + excluded.cost_usd",
                (account_id, _today(), calls, input_tokens, output_tokens, cost_usd),
            )

    def usage_today(self, account_id: int) -> dict[str, Any]:
        with self.read() as conn:
            row = conn.execute(
                "SELECT * FROM usage_daily WHERE account_id = ? AND day = ?",
                (account_id, _today()),
            ).fetchone()
        return dict(row) if row else {
            "account_id": account_id, "day": _today(), "calls": 0,
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
        }

    def usage_all_accounts_today(self) -> dict[str, Any]:
        """The global cap's input. A hosted app spends money when strangers use it."""
        with self.read() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(calls),0) AS calls,"
                " COALESCE(SUM(input_tokens),0) AS input_tokens,"
                " COALESCE(SUM(output_tokens),0) AS output_tokens,"
                " COALESCE(SUM(cost_usd),0.0) AS cost_usd"
                " FROM usage_daily WHERE day = ?",
                (_today(),),
            ).fetchone()
        return dict(row)

    # ----------------------------------------------------------------- export

    def export_account(self, account_id: int) -> dict[str, Any]:
        """Everything the user put in, in one JSON-serialisable object.

        Deliberately omits ``passphrase_hash`` and the agent execution log's internals —
        the first because it must never leave the database, the second because it is ours,
        not theirs. Token totals are included; the user paid for them in attention.
        """
        account = self.get_account(account_id) or {}
        return {
            "exported_at": _now(),
            "account": {k: v for k, v in account.items() if k != "passphrase_hash"},
            "domains": self.list_domains(account_id, include_archived=True),
            "people": self.list_people(account_id),
            "criteria": self.list_criteria(account_id, status="all"),
            "entries": self.list_entries(account_id, limit=10_000),
            "observations": self.list_observations(account_id, limit=10_000),
            "patterns": self.list_patterns(account_id, status="all"),
            "decisions": self.list_decisions(account_id, limit=10_000),
            "usage_today": self.usage_today(account_id),
        }
