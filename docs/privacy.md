# KRYteria — privacy architecture

> **KRYteria is a private space between a person and their AI agent. No other person can
> know whether they have been discussed, assessed, or entered into KRYteria.**

This is a product requirement, not a compliance afterthought. People write things here
they would not say to a friend, a partner, a therapist, or out loud to themselves: sex,
attraction, rejection, abuse, money, doubt, things they are embarrassed to admit. The
architecture has to earn that.

This document states what is **built**, what is **not built**, and what is **outside our
control**. The third category is the one most products get wrong by omission.

---

## The eight principles

1. **Private by design.** User information is accessible only to the authenticated user,
   and processed only by the services necessary to provide KRYteria.
2. **No interpersonal disclosure.** KRYteria never tells another person that they have
   been mentioned, assessed, or discussed.
3. **No sharing mechanisms.** No social, collaborative, or person-to-person sharing.
4. **User-controlled retention.** Users decide whether their original Brain Dumps and
   associated conversations are retained.
5. **Data minimisation.** Information not needed for the requested functionality is not
   collected or stored.
6. **User-controlled deletion.** Users can delete retained information, with deletion
   behaviour and backup expiration documented.
7. **No model training on private reflections.** Brain Dumps are not used to train models.
8. **Transparency.** Users are told what is processed, what is stored, where it goes, and
   for how long.

---

## 1. No sharing, no signalling, no discoverability

**Being mentioned in KRYteria is indistinguishable, to the person mentioned, from never
having been mentioned at all.**

Not built, and not to be built:

- Sharing Brain Dumps, assessments, profiles, observations or histories with another user.
- Shared profiles, collaborative assessments, partner invitations.
- Notifying anyone that they appear in somebody's journal — positive, negative or neutral.
- Any "you've been mentioned" mechanism.
- Searching for or discovering whether another user has a profile about you.
- Cross-user matching, comparison, or visibility into another person's activity.
- Disclosing one user's information to another — **including when both are real users who
  happen to be dating each other**.

A notification as mild as *"someone added you to their dating journal"* would break the
premise entirely. There is no mechanism that could generate that signal, because there is
no code path from one account's data to another account's anything.

**How this is enforced rather than promised.** There is no API route that accepts another
user's identifier. Every route resolves the account from a signed session cookie —
`backend/api/deps.py` — so a route *cannot* be pointed at somebody else's rows. People are
stored as **user-chosen aliases**; there is no column for a real name, no email on a
person record, nothing that could match one user's "Sam" to another user's account.

---

## 2. Authorisation at the database layer, not only the API

Every store method that takes a row id also takes the account id and scopes its SQL.
`Store._assert_owns` raises `NotOwned`, and the HTTP layer turns that into **404, never
403** — confirming that a row exists but belongs to somebody else is itself a disclosure,
and here it could tell one person that another is journalling about them.

This is deliberately redundant with the API's own guards. The API layer is the first line;
this is the one that holds when somebody adds a route and forgets.

Covered by `tests/test_offline.py::test_store_refuses_cross_account_reach` (one account
attempting nine operations against another's rows) and
`tests/test_api.py::test_data_isolation` (the same over HTTP).

---

## 3. What is kept, and who decides

| Data | Default treatment |
|---|---|
| Original Brain Dump text | **Erased after processing** |
| Structured observations and analysis | Retained |
| Quoted claims in follow-up questions | Retained — but see below |

Three retention modes, set once in settings and overridable per dump:

- **`discard`** — the narrative *and everything derived from it* are erased.
- **`analysis_only`** *(default)* — the narrative is erased; observations, mappings and
  assessments survive.
- **`keep_all`** — everything stays until deleted.

`analysis_only` is the default because keeping the most sensitive thing in the product
should not require an opt-out. Somebody may want to keep the fact that they noticed a
pattern of inconsistent communication without keeping the intimate 2,000-word account they
wrote at 1 a.m.

**What erasure actually does.** `store.apply_retention` overwrites `body` and every
structured field with `NULL` — not blanked, not tombstoned with its length, not kept "just
in case". The entry row survives as a dated placeholder so surviving observations still
have something to point at.

**Why `discard` also removes derived records.** An extracted observation can be a
near-quotation — *"She stayed rather than have another argument"* — and an interrogation
stores the user's claim verbatim by design. Keeping those after somebody asked for the
narrative to be discarded would honour the letter and break the promise.

Retention is applied **in the same request as processing**, so the window in which an
unwanted original sits in the database is the length of one HTTP call, not until a nightly
sweep. `store.erase_originals` exists as a backstop and for applying a changed default to
what was already written.

`GET /api/retention` reports what is actually stored, counted from the data rather than
asserted.

---

## 4. Telemetry carries no private writing

Agent orchestration, token accounting and debugging work without recording what anybody
wrote.

- `agent_steps` records agent name, model, provider, prompt version, token counts, cost,
  latency, and tool **names with argument keys** — never argument values.
- Error messages are **redacted before storage** (`agents/base.redact_error`). A Pydantic
  `ValidationError` embeds the offending `input_value`, which for these models is agent
  output paraphrasing the narrative; the stored message keeps the exception type, the
  field, and the rule broken, and drops the value.
- Unhandled exceptions return one sentence to the browser. A stack trace from a
  journalling app can contain the user's own words.
- The schema comment above `agent_steps` states the rule, because that table is shown on
  screen and pasted into reports — exactly where private writing would leak while looking
  like harmless telemetry.

---

## 5. The AI provider — what we do not control

**This is the part a product should not overclaim, so it is stated plainly.**

Even when KRYteria erases the original after processing, **the model provider received it
in order to process it.** Our erasure governs our database. It does not reach back into
anybody else's.

Current chain: KRYteria backend → Portkey → the model (`gpt-6-luna`).

**Not yet established, and required before any claim is made to a user:**

- Portkey's retention and logging policy for request and response bodies, and whether a
  zero- or minimal-retention configuration is available on this account.
- The upstream provider's retention, logging, and training policy.
- Whether a no-training guarantee applies to this tier of access.

Until those are confirmed in writing, KRYteria must **not** tell anyone their data is
never retained anywhere. The honest statement is: *KRYteria erases what you asked it to
erase from KRYteria's own storage; your reflection is sent to a model provider in order to
be read, and their policy governs what happens there.*

Mitigations already in place: nothing identifying is sent — people are aliases, accounts
are anonymous, and the prompts contain no account handle, email, or real name.

---

## 6. Deletion

- `POST /api/account/delete` removes everything. Rows are **deleted, not flagged**;
  `ON DELETE CASCADE` carries it through every child table.
- It requires the passphrase and a typed confirmation, because a journal like this is
  exactly the kind of data somebody might be deleting under pressure from another person,
  and a stray click should not do it.
- `GET /api/export` returns everything first, and omits the passphrase hash.

**Backups.** There are none. The database is a single local SQLite file with no backup or
replication configured, so there are no copies to expire. **If backups are ever added, a
documented expiration policy must be added at the same time, and this section updated** —
the deletion promise is only true while this paragraph is.

---

## 7. Not built, by design

- No analytics, telemetry service, crash reporter, or third-party script.
- No training on user content.
- No password or identity beyond an anonymous handle.
- No email, phone number, or contact detail is collected anywhere. Account recovery is a
  **code issued once at sign-up**, hashed with Argon2id and stored only as a hash, rather
  than a reset link sent to an address. That keeps the account anonymous and, more to the
  point here, means there is no message about this application that can arrive somewhere
  another person can see it.

---

## 8. What is still missing

Honest gaps, so nobody reads this document as a completed checklist:

- **Provider retention is unconfirmed** (section 5). The largest open item.
- **The privacy promise is not yet visible in onboarding.** It must be shown when somebody
  signs up, not buried in terms — the front end does not exist yet.
- **No encryption at rest.** SQLite on disk. The README says so and does not claim
  otherwise.
- **`interrogations.claim` stores the user's words verbatim** by design, so a follow-up
  question can quote them accurately. It is removed by `discard` but survives
  `analysis_only`, which means `analysis_only` retains *some* original phrasing. This is a
  real limitation of the middle setting and should be surfaced in the UI rather than left
  for somebody to discover.
