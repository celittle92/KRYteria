# KRYteria — engineering record

What was built, why it is shaped this way, and how to check any of it yourself.

The verbatim prompt history is in [`../AI_prompts.md`](../AI_prompts.md). The argument
for the product is [`../report.html`](../report.html). This file is the engineering:
decisions, their reasons, and the command that verifies each claim.

**Project.** KRYteria is a decision mirror. It helps a person compare three things: what
they say they want, what they are actually experiencing, and what they are choosing to do
about it. It is not a compatibility score, a red-flag detector, or a chatbot that agrees
with you.

| | |
|---|---|
| Live | <https://kryteria.onrender.com> — nine demo characters, one click each, nothing to type |
| Repository | <https://github.com/celittle92/KRYteria> |
| Model | `gpt-6-luna`, **pinned** in `app_config.REQUIRED_OPENAI_MODEL` — `OPENAI_MODEL` is read but cannot win |
| Provider | Portkey, via `app_config.py`; `PORTKEY_API_KEY` from `.env` here, one level up, or the process environment |
| Backend | FastAPI + SQLite, hand-written repository layer, 41 modules, 34 tables |
| Agents | 7 PydanticAI agents, 8 runtime prompts in `backend/prompts/` |
| Front end | React 18 + Vite + TypeScript + Tailwind, 10 screens, `dist/` committed |
| Tests | 5 suites, **1,340 checks**, all offline, no API key, no network |
| Spend | 12 live runs, 11 of them fully measured: 314 calls, **$0.186** — `output/usage_log.json` |

---

## 1. The data model is the product

Built first and deliberately: *"If that data model is wrong, the pretty interface won't
save us."*

**Three levels.** A **Master Criteria Library** holds the user's reusable standards, each
carrying **no tier and belonging to no profile**. **KRYteria Profiles** select criteria
from that library and assign *this profile's* tier. **Assessments** judge evidence about
one person against **one** profile.

That separation is what makes the Jimmy G Principle structural rather than aspirational:
adding a fourth profile never edits a criterion, and `get_assessment` cannot fall back to
another profile's answer.

**Two independent dimensions.** Importance (`mandatory` / `preferred` / `aspirational`) is
a property of a criterion *within a profile*. Status (`pass` / `unknown` / `fail` /
`not_applicable`) is what is known about one person against it. A Mandatory criterion can
sit at Unknown indefinitely; `not_applicable` is a real answer and never a failure.

**Criteria are versioned, never overwritten.** A revision writes a new version and
supersedes the old one. This is what lets the product notice that a standard quietly got
easier — destroy the history and that insight is gone.

```bash
python3 tests/test_offline.py        # 512 checks, needs no packages at all
```

---

## 2. Architecture: a controlled workflow, not a chat mesh

Seven specialists under a **deterministic orchestrator**. They do not talk to each other;
the orchestrator routes and they return validated data to it. A deliberate choice against
HW5's delegation mesh — easier to debug, cheaper to run, explicable in a diagram.

```
brain dump text
      │
  Orchestrator ── routes · budget caps · execution log. Makes NO model call.
      │
  Narrative ║ Safety        ← concurrently, both on the RAW text
      │
  Evidence                  ← maps observations → criteria, within one profile
      │
  Reasoning                 ← only when the writer stated a conclusion
      │
  Reflection                ← only when asked for
```

**Safety is a peer, not a filter.** It runs alongside Narrative on the raw text, never
downstream of a mapping that might have normalised something. `safety_events` has no
`profile_id` column and `log_safety_event` takes no profile argument — asserted by a test
that inspects the function signature, so nobody can add one.

**Narrative and Evidence are separate on purpose.** Pulling observations out of a
narrative and deciding which criteria they bear on are different jobs; merging them is how
an interpretation quietly becomes a mapping. Narrative holds no criteria tools at all — it
cannot decide what an observation says about somebody's standards because it has not been
told what those standards are.

**One agent audits another.** Reasoning is handed Evidence's mappings and told they are
claims too. The failure it catches is quiet: a criterion says one word, the entry says a
different word, and the mapping treats them as the same. *Soft hands* against *"his hands
are extremely nice"* — nice is not soft, and whether they are the same thing is the user's
call. This fires 22 times across the demo.

```bash
.venv/bin/python tools/trace_one.py jane-money-3        # estimate only
.venv/bin/python tests/test_contracts.py                # output contracts
```

---

## 3. What the code enforces rather than asks for

The difference between a principle and a prompt instruction is whether code can violate
it. These cannot.

| Promise | Mechanism |
|---|---|
| A citation cannot be fabricated | `research_ref` must resolve to a **verified** row; `link_evidence` refuses otherwise |
| No agent moves an assessment | Agents write proposals; one route moves a status and a person operates it |
| Safety never depends on a profile | `log_safety_event` takes no `profile_id`; a test reads the signature |
| No user can learn of another | Every query is scoped by `account_id`, so another account's row is simply *not found* and the route answers **404, never 403** — confirming a row exists but belongs to somebody else is itself a disclosure here. `NotOwned` covers the store methods that raise rather than return nothing |
| A thin pattern cannot overclaim | Below three distinct entries it cannot exceed `insufficient`; a confident finding must offer an alternative |
| Sources must be reputable | `backend/sources.py` is an allowlist, enforced on both the add and verify paths |
| A profile is never deleted | Rename and archive only; a test asserts the delete route does not exist |

**Why an allowlist and not a blocklist.** A blocklist is a list of the bad sites somebody
already thought of, and the one that matters is always the one nobody listed. An allowlist
is wrong in the safe direction. Note `academia.edu` is explicitly refused — the `.edu`
belongs to the company, which is why a naive suffix test is not enough.

---

## 4. Safety

**Record everything; withhold the analysis from the screen.** On `disclosure` or
`immediate_danger`, Narrative, themes and Evidence still run and persist; Reasoning and
Reflection are skipped; the screen shows the safety response and nothing else. Until this
was fixed the orchestrator returned *before* `save_observations`, so the entry a user was
most serious about was the one KRYteria recorded least.

`WITHHOLD_ANALYSIS_AT` is checked **in code**, not read off `suggested_action` — that
field comes from the same model call that classified the concern, and letting it also
decide whether to stop means one misjudgement loses both.

**Resources are curated and never invented.** Every row carries `source_url` and
`verified_at`, shown to the user, because a dated number can be judged and a bare one asks
for trust nobody earned. Three services are excluded with recorded reasons and a test
keeps them out until each reason is resolved.

**Location is never inferred.** `accounts.region` is user-set. No IP lookup, no
`X-Forwarded-For`, no timezone guess. A test sends spoofed location headers and then walks
the AST of every route module to confirm nothing touches the request except `cookies` —
checked by *mechanism*, not by header name.

**A gap found by evaluation, not by a crash.** A region-less account disclosing physical
harm was offered nothing. No single behaviour was wrong: GLOBAL-only for an unset region
is right, withholding emergency numbers below `immediate_danger` is right, and the only
GLOBAL row was an emergency number. Three correct rules composing into a wrong outcome.
Fixed by adding a global *directory* — see
[`../docs/safety_resources_decision.md`](../docs/safety_resources_decision.md).

```bash
.venv/bin/python -m backend.run_evals safety        # estimate; live costs money
```

---

## 5. Privacy is P0, above the schema

> KRYteria is a private space between the user and their AI agent. No other person can
> know whether they have been discussed, assessed, or entered into KRYteria.

Authorisation lives at the **database layer**, redundantly with the API's own guards:
that one is the first line, this one holds when somebody adds a route and forgets. The
mechanism is scoping rather than checking — a query carrying somebody else's
`account_id` returns nothing, so there is no moment at which the code holds another
user's row and has to decide what to do with it.

**Retention runs in the same request as processing**, so an unwanted original exists for
the length of one HTTP call. `discard` also removes derived records, because an extracted
observation can be a near-quotation.

**Telemetry carries no private writing.** `agent_steps` holds tool names and argument
*keys*, never values; errors go through `redact_error` first, because a Pydantic
`ValidationError` embeds the offending input — which here is agent output paraphrasing the
narrative.

**Accounts are anonymous, with a recovery code rather than an email.** A lost passphrase
would otherwise mean months of someone's writing gone. An email would fix that by adding
the one thing this app is designed around: a real identity on file and a notification
channel visible to anyone with access to that inbox. A six-word code, Argon2id-hashed like
a passphrase because anything that can reset a passphrase opens the journal, consumed on
use.

**Do not overclaim the provider chain.** Erasure governs this database only. Portkey's and
the upstream provider's retention policies are unconfirmed; `docs/privacy.md` §5 holds the
open questions.

---

## 6. Security

Three gaps, all of which the app shipped with, all found by review rather than incident.

**Sessions did not expire.** `URLSafeSerializer` signatures are valid forever; the
`max_age` on `set_cookie` is an instruction to the *browser* about when to stop sending a
value, not a statement about when it stops being accepted. A copied cookie worked
indefinitely, including after sign-out. Now `URLSafeTimedSerializer`, 14 days, enforced
server-side.

**No security headers at all.** CSP, X-Frame-Options, nosniff, Referrer-Policy,
Permissions-Policy, COOP/CORP, and HSTS only when actually serving https.
`frame-ancestors 'none'` is the load-bearing one: framing is how somebody with access to a
shared device could overlay or watch this interface.

**No brute-force protection.** Throttled **per handle, not per IP** — an IP is a location,
and this app promises twice over that it never infers one. The trade is stated rather than
hidden: this does not stop one passphrase sprayed across many handles. A correct
passphrase is also refused during cooldown, a success clears the counter, and it never
disables an account, because lockout against a known handle would be a denial-of-service
primitive.

```bash
.venv/bin/python tests/test_api.py        # 273 checks, including all of the above
```

---

## 7. Evaluation, and keeping the instrument honest

31 cases across `safety_evals.json` and `reasoning_evals.json`, driven by
`backend/evals/`. Four rules keep it honest: **the harness refuses rather than skips**;
**`manual` is a real outcome and never a pass**; **no LLM judge**, because that would be
our model grading our product against our rubric; and **demo mode cannot produce
evidence**, enforced by diverting its output to `output/demo_runs/`.

**The recurring lesson, now twice over: the instrument was wrong more often than the thing
being measured.** Of five failures in the live reasoning run, four were the harness:

- A case that could not pass by construction, because eval accounts set no region and the
  only global resource was one the policy correctly withholds.
- Two cases failing `prose_lacks` on text doing exactly what the case tested for — a
  question the product *asks* is not a thing it *asserts*.
- A detector whose answer depended on sentence length: the lookback window was 48
  characters, so the same attribution was caught in a short sentence and missed in a long
  one.

And one failure that could not be adjudicated at all, because the artefact stored
observations as a *count*. Evidence that cost money has to be complete — the same lesson
an earlier prose truncation had already taught.

**Never change the thing under test to make the test pass.** The one genuine product
failure found this way was routing: `needs_interrogation` was a keyword list, so
*"He's completely unreliable, I can't count on him for anything"* matched none of 18
keywords and Reasoning never ran. Across the 36-text corpus the old rule fired 4 times,
and only 3 of 13 adversarial cases reached the agent they were written to test. Fixed by
routing on stated conclusions, at a measured +53% per entry.

---

## 8. The demo: nine characters, and why it is JSON

Nine accounts in a shared fictional ecosystem. Character data lives in
`data/characters/*.json`, not Python, because the thing most needing review is the
*narrative* — whether an entry actually supports the assessment attached to it — and that
review belongs to whoever wrote the characters.

**The analysis is real.** Fourteen proof-point entries carry no hand-written observations;
they were run through the live pipeline and the output frozen into the character files
under a `generated` key. The hosted deployment rebuilds from those files on every boot, so
analysis living only in a database would be regenerated on every restart — at $0.043 a
time, a bill with no ceiling.

**The seeder is the one component that could break the privacy promise**, because it is
the only thing holding all nine accounts open at once. `assert_no_cross_account_links`
runs after every build and fails if it examined no tables, because a check that silently
inspects nothing reads as a pass.

```bash
.venv/bin/python -m backend.seed_characters --check     # validate, no database
.venv/bin/python -m backend.seed_characters --reset     # rebuild all nine
```

---

## 9. Deployment

One image, one process, one port — the app serves its own built front end, so there is no
second service and no CORS. The `Dockerfile` **pins the interpreter**, because "works
locally, wrong minor version in production" is the most common way a deadline deploy
fails.

A free instance **sleeps** after ~15 minutes and has an **ephemeral disk**.
`KRYTERIA_SEED_ON_BOOT` turns the second into a non-event: the demo is rebuilt on every
boot, so a grader never meets an empty app. The first is stated in the UI rather than
hidden — a loading state that explains the wait, with a retry, because the first request
from a new browser is the one most likely to lose the race with the boot.

| Variable | Purpose |
|---|---|
| `PORTKEY_API_KEY` | Supplied by the host; never committed or baked into a layer |
| `KRYTERIA_DB_PATH` | Outside the source tree, so a redeploy cannot replace somebody's journal |
| `KRYTERIA_SECRET_KEY` | Signs sessions. **Set in production** — the dev fallback regenerates per process |
| `KRYTERIA_SECURE_COOKIES` | `true` over https |
| `KRYTERIA_SEED_ON_BOOT` | Rebuild the demo at startup |
| `KRYTERIA_MODE` | `demo` runs free and simulated; otherwise live when a key is reachable |

---

## 10. Verifying all of it

```bash
python3      tests/test_offline.py      # 512 — store layer, needs no packages
.venv/bin/python tests/test_contracts.py    # 125 — output contracts, demo provider
.venv/bin/python tests/test_wiring.py       #  74 — Argon2id, provider, budget caps
.venv/bin/python tests/test_api.py          # 273 — HTTP, isolation, security, retention
.venv/bin/python tests/test_evals.py        # 353 — the harness, mostly that it REFUSES
```

All five are free, offline, and need no API key. **Live runs cost money and refuse to
start without `--yes-spend-credits`, after printing the call count.**

### Known limits, stated rather than discovered

- **Cache writes are not modelled** — the provider does not report them separately, so
  every cost figure is slightly low on a cold cache and correct once warm.
- **One research entry stays pending.** Its containing volume is confirmed; nothing found
  places the chapter in it. Promoting it to round the number up would be the most
  corrosive thing anyone could do to that layer.
- **`proposed_by` cannot distinguish fixture from agent.** The column allows `'agent'` or
  `'user'`, so hand-written demo evidence is stored as `'agent'`. The character files
  distinguish them; the database does not. Fixing it is a schema bump.
- **No migrations.** A schema change requires deleting the database and re-seeding, and
  `Store()` refuses to open a stale one rather than failing later. Right trade with no
  real users; needs Alembic before anybody's journal depends on it.
- **A hosted free instance is not durable storage**, and the README says so rather than
  implying otherwise.
