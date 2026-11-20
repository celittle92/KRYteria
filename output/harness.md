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
| Tests | 5 suites, **1,597 checks**, all offline, no API key, no network |
| Spend | 19 live runs — 17 with token counts, 16 with a cost: 340 calls, **$0.210** — `output/usage_log.json` |

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
python3 tests/test_offline.py        # 582 checks, needs no packages at all
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
downstream of a mapping that might have normalized something. `safety_events` has no
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
| The writer's own conduct is not evidence about somebody else | Every observation carries `about`; an entry that is mostly `me` is named as such to Evidence and Reflection rather than converted into questions about the other person |
| One entry cannot become a page of rows | `EvidenceOutput` collapses duplicate (observation, criterion) pairs and keeps one unsettled note per criterion |
| The app never writes the user's standards | A pasted list is parsed deterministically in `backend/paste.py` — **no model call** — and a line that only names a standard becomes a criterion with an empty `desired_behavior` rather than an invented sentence |
| Bulk convenience assigns no importance | `add_criteria_to_profile` puts everything at one neutral tier and leaves settings already chosen alone; Mandatory is the user's statement about what is disqualifying |

**Why an allowlist and not a blocklist.** A blocklist is a list of the bad sites somebody
already thought of, and the one that matters is always the one nobody listed. An allowlist
is wrong in the safe direction. Note `academia.edu` is explicitly refused — the `.edu`
belongs to the company, which is why a naive suffix test is not enough.

**The burden-shift, found by running the product rather than reading it.** On 2026-11-18
the author wrote a Brain Dump into a demo account from the perspective of a writer
describing *his own* inconsistency — unanswered messages, unpredictable hours, no settled
view of what he was willing to change — and read what came back. Twenty-five mapping rows,
most of them `complicating`, most ending *"…but this does not establish whether she can
live with it."* Questions about whether she keeps a tally and whether discussing things
with her becomes a fight. **He wrote about himself and got back a page of doubts about
her.**

The mechanism is worth recording because it is not the obvious one. Those phrases were not
invented: *"instead of keeping a tally"* and *"without it becoming a fight"* are clauses of
**his own criteria**, in his own words. The pipeline had no representation of *whose
conduct a sentence describes*, so every sentence about him was matched against criteria
that describe her, and his own standards were read back as open questions about a woman who
had done nothing in the entry. `ExtractedObservation.about` is the fix at the contract
level; the behavioral rules live in `narrative.md`, `evidence.md`, `reasoning.md` and
`reflection.md`, with regression cases `bur-01`, `imp-01` and `ovm-01`.

**The correction had its own failure mode, which is the part worth keeping.** Verified by
re-running the same entry live — the only way to check a prompt change — the fix worked
and introduced two faults. One question was built on a premise the entry did not contain
(*"you've decided to tell Catherine…"*), the same imputation failure pointed at the
**writer**, because the rule forbade inventing a behavior for the person being assessed
and said nothing about the person writing. And four *correct* mappings were lost: his
description of her intelligence, career and humor arrived as one `emotional_reaction`
marked `me` and were not mapped at all. Both are closed and confirmed by a third run.
`narrative.md` now **splits a sentence that does two jobs** — his feeling (`me`) and what
it reports about her (`them`), because qualities count and not only actions — and
`evidence.md` records that **some criteria are about the writer's own experience**
(*Physical attraction*, *chemistry*), which a `me` observation answers rather than fails.
Regression cases `imp-02` and `lst-01`, failure mode `evidence_loss`.

One of the two causes was not in a prompt at all: `agents/evidence._ABOUT["me"]` ended
*"not evidence about the other person"*, an absolute printed beside every observation and
sitting closer to the model than the nuance it contradicted. **A label says what a thing
is; what to do with it belongs where the exceptions can live.**

**Getting a list in, without the app editing it.** Added 2026-11-17, after the author made
her own account and hit the wall in minutes: somebody who already knows what they want has
usually already written it down, and typing it back one field at a time is where they
leave. `POST /api/criteria/parse` reads a pasted list and **writes nothing**;
`POST /api/criteria/bulk` creates the rows she approved, in one transaction. The parse step
is deliberately not a model call — a model asked to tidy somebody's standards will improve
them, and the Criteria agent's indicator suggestions are a thing she opts into, not
something that happens silently to twenty rows. `backend/paste.py` therefore appears in no
`scripts` entry of `submission_spec.json`, because it loads no prompt and should not
pretend to. It refuses rather than truncates: an over-long line is reported, never cut
down, and an unsplittable one is kept whole as the value rather than guessed at.
`POST /api/profiles/{id}/criteria/bulk` is the matching move at the profile level.

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
harm was offered nothing. No single behavior was wrong: GLOBAL-only for an unset region
is right, withholding emergency numbers below `immediate_danger` is right, and the only
GLOBAL row was an emergency number. Three correct rules composing into a wrong outcome.
Fixed by adding a global *directory* — see
[`../docs/safety_resources_decision.md`](../docs/safety_resources_decision.md).

**A question needs an answer, and a rule needs a wire** (2026-11-20). Christine ran a
Brain Dump of her own about a pushy date the previous summer and hit a dead end: the halt
screen asked *"Are you safe right now?"* and offered nowhere to say anything back. Her
words: *"I don't get to interact with the app in any way to tell it that I am safe, or to
keep working with the app. It feels like a blocker."*

The halt was right; the silence after it was not. The charter's own over-response rule
says a person should be able to tell KRYteria something terrible happened *"without
feeling like they've triggered a machine that no longer knows how to talk to them"* — and
a screen that asks whether you are safe and then stops is that machine.

Four answers now, recorded on `safety_events.user_response`: **I am safe · This is a past
experience · I need support · I'd rather not say.** The fourth matters as much as the
first, because the charter forbids pressing for disclosure and a screen only honors that
by making "I'd rather not say" a thing you can press rather than the absence of one. The
buttons appear only where the model actually asked a safety question — four of them under
a `potential` concern that raised none would be the over-response failure.

**Answering never disarms the safety layer.** *"I was safe in August"* is not a statement
about December, and a layer a past answer can switch off fails open on exactly the cases
it exists for. It closes the loop on one entry and nothing more. There is a test.

**Two further defects surfaced by following the first one.**

- The *"I don't need these"* button set React state and called nothing. `respond_to_offer`
  existed, the route existed, and `should_offer_resources` implemented the charter's *"a
  user's refusal of resources must be respected"* — **the rule was unreachable from the
  screen.** The orchestrator was also discarding the offer id that `record_resource_offer`
  returned, so the browser had no identifier to answer with. Now wired. Verified by
  declining on one entry and watching the next halt fire, ask, and volunteer nothing.
- The API had always computed the sentence telling her the analysis was *kept* — plus the
  counts and where to find it — and the browser threw all of it away. The one promise the
  halt makes was the one thing she could not see.

**The copy carries no fact that can go stale**, and this is the design rather than an
accident of wording. Christine drafted a support reply and then objected to her own draft:
*"I actually don't like that reply because we clearly cannot keep it up to date."* She is
right — verifying six countries on 2026-11-12 found two dead government pages, a site
down, and an organization contradicting itself about its own number. So the acknowledgment
opens a door and holds no knowledge: *"KRYteria is not a crisis service and won't pretend
to be one, so here is what it actually has."* The knowledge lives where it can be dated —
the curated directory, every row showing when it was last checked, and an empty one saying
plainly that nothing is verified rather than inventing something. Underneath is
`EMERGENCY_NOTE`, which names no digits because she knows her own emergency number better
than this app does. A test asserts the acknowledgments contain no digit, no named
service, and no availability claim.

**The level is floored in code, not only asked for in the prompt** (2026-11-20). Settling
two open eval decisions with one live case exposed a third thing: a threat tied to leaving
came back at `pattern`, which is below `WITHHOLD_ANALYSIS_AT`, so the orchestrator did not
halt and carried on into ordinary compatibility analysis — the charter's flattest
prohibition. `pattern` means *repeated*; one incident was described.

The prompt was the cause, one bullet from where it was the cause last time: the
strangulation bullet ends *"Record these at `disclosure` at minimum"* and the threats
bullet named no level at all. Both halves are fixed. `SafetyOutput.escalation` is now a
**closed vocabulary** of the five escalating behaviors the charter already described in
prose, and `CONCERN_FLOOR` raises the level to the floor each requires, tagged
`policy:level_floored` in the trace. It only ever raises, and it supplies rather than
rejects, like `ALWAYS_CHECK_SAFETY` and for the same reason.

**It is deliberately not a keyword gate.** Recognizing *"a threat tied to leaving"* from
the words is the mistake this project has made three times; the model recognizes and the
code floors. Confirmed live: `coercive_control` / `disclosure`, `halted: True`, three
calls rather than five because Reasoning and Reflection are skipped on a halt.

**Both resource files re-verified 2026-11-20**, the standing rule before a demo and before
submission. Thirteen of fifteen rows confirmed by fetching each organization's own page and
checking that the number we print still appears on it; their `verified_at` moved to that
date and their `verification_note` says exactly what was checked and that the **hours
wording was not re-read** on this pass. The two that refuse automated fetching — RAINN and
911.gov, HTTP 403 again — keep their 2026-11-16 dates, the last time a person opened them,
with the attempt and its failure recorded on the row. **The gap there is provenance, not
accuracy**, and back-dating it would be the lie the dated field exists to prevent.

```bash
.venv/bin/python -m backend.run_evals safety        # estimate; live costs money
```


### Spelling: the app's voice is American, the agents mirror the writer

Christine, 2026-11-20: *"everything was crafted using British English but I am an
American."* True since the first file, and fixed in two different ways because there are
two different things here.

**Authored text is American** — the UI copy, the report, the deck, the README, the demo
characters' entries. That is Christine's voice, and it should be hers.
`tools/americanize.py` did the sweep with explicit word pairs rather than suffix rules: a
rule that turns `-ise` into `-ize` also eats *surprise* and *premise*, and one that turns
`-re` into `-er` eats *genre* and *acre*. It protects four things — identifiers and routes,
archived model output, quotations, and the research pack — and the dry run earned two of
those protections by catching `onClick={analyse}` and the `GENERALISING` constant that a
test imports by name.

**Generated text mirrors the writer**, which was Christine's correction to my first
attempt: *"i mean it should use the same spelling as the user...i'd think."* Right, and
better. Every prompt now says to match the spelling conventions of the person whose entry
it is reading, falling back to American where an entry is too short to tell. A British or
Australian user gets their own spelling back, because the product's whole position is that
the record belongs to the person who wrote it — and a record that silently re-spells
somebody's world is not quite theirs. A register instruction, not a judgment one, so it
does not break the freeze on agent reasoning.

**What was deliberately left British:** `acknowledgement` (a Pydantic field the prompts
instruct the model to emit, the API returns, the front end reads and the tests assert on)
and `/api/entries/{id}/analyse`. Renaming either is a coordinated change across five layers
whose failure mode is a validation error inside the **safety** step — a layer that fails
open on the cases it exists for. The cost is an internal key nobody reads. Organization
names and quoted text in the resource files stay exactly as those organizations write them,
because a service's name is not a spelling choice.

---

## 5. Privacy is P0, above the schema

> KRYteria is a private space between the user and their AI agent. No other person can
> know whether they have been discussed, assessed, or entered into KRYteria.

Authorization lives at the **database layer**, redundantly with the API's own guards:
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

Six gaps, all of which the app shipped with, all found by review or audit rather than by
incident. The first three came from one review, and each of the three after it was found
by going back and looking again — which is the honest summary of how this section grew.

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

**And a fourth, found later by audit: sign-up was not throttled.** This module's own
docstring had said all along that it covered sign-up, sign-in and recovery; the sign-up
route never called it. That left the one endpoint running Argon2id unconditionally as the
cheapest way to make the app do expensive work, and made *"that handle is taken"* an
unmetered way to test whether a handle exists. A docstring is not an enforcement
mechanism, which is the whole argument of §3.

**A fifth, in the privacy layer rather than the security one.**
`record_checklist_observation` took `account_id` and only *stamped* it on the row — it
never checked it — and `list_checklist`'s count query grouped by item and person with no
account at all. A write from one session could therefore be counted onto another
account's screen, which is the one thing this product says is structurally impossible.
Reproduced with two accounts, fixed in both places, and pinned by
`test_another_account_cannot_plant_or_see_a_checklist_observation`. **Stamping an id is
not the same as asserting it**, and the two read almost identically at a glance.

**A sixth, inside the throttle itself: a fresh handle met no limit at all.**
`throttle.check` is keyed on the handle being attempted and `record_success` clears that
key, so a script posting a new handle every time was never slowed. Unlimited account
creation is a lever on the only resource this app spends — the per-account cap is 120,000
tokens a day and the global cap is 2,000,000, so **about seventeen new accounts exhaust
the global budget** and then nothing analyzes for anybody until midnight UTC. The money
was never the exposure; that cap holds the worst day near a dollar. Availability was.
`throttle.check_new_account` now bounds creation for the application as a whole — 12 an
hour, 40 a day, two windows because an hourly bound alone can be trickled under at six an
hour. It has **no key**, for the same reason the counter above is keyed on a handle
rather than an IP. A keyless limiter is itself a denial-of-service primitive, so the
justification has to be that tripping it costs little: the whole demo opens in one click
and needs no account, and it refuses *creation* while leaving every existing user's
sign-in, journal and analysis untouched.

```bash
.venv/bin/python tests/test_api.py        # 333 checks, including all of the above
```

---

## 7. Evaluation, and keeping the instrument honest

36 cases across `safety_evals.json` and `reasoning_evals.json`, driven by
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

And one failure that could not be adjudicated at all, because the artifact stored
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
python3      tests/test_offline.py      # 582 — store layer, needs no packages
.venv/bin/python tests/test_contracts.py    # 224 — output contracts, demo provider
.venv/bin/python tests/test_wiring.py       #  74 — Argon2id, provider, budget caps
.venv/bin/python tests/test_api.py          # 333 — HTTP, isolation, security, retention
.venv/bin/python tests/test_evals.py        # 384 — the harness, mostly that it REFUSES
```

All five are free, offline, and need no API key. **Live runs cost money and refuse to
start without `--yes-spend-credits`, after printing the call count.**

### Known limits, stated rather than discovered

- **Cache accounting is incomplete in both directions.** Cache *writes* are not modeled
  because the provider does not report them separately, so figures are slightly low on a
  cold cache. And no artifact preserved a cached-*input* count, because `trace_one.py`
  and the usage log printed input, output, latency and cost but not that column — the
  §4 traced run's recorded cost implies about 5,140 cached tokens that nothing wrote
  down. The column is recorded as unknown, never as zero, and `trace_one.py` now prints
  it.
- **Answers to interrogation questions are recorded but never re-read.** Answering a
  *worth pinning down* question writes to `interrogations.answer`, and the answer shows on
  its entry in the Journal under *"You said"*. **No agent consumes it.** Christine found
  this by answering one and watching it disappear — *"I didn't see anything happen with
  it. What happens? Why would someone answer it? Where does the answer go?"* Half of that
  was a UI defect and is fixed: the screen now confirms the save and says where the answer
  lives, because a product whose subject is evidence cannot make somebody guess whether
  their own words were kept. The other half is real and is this limit. Feeding answers
  into the next analysis is the obvious next step and the right shape — the user supplying
  the missing detail is exactly what Evidence Interrogation asks for — but it changes
  agent *input*, which is the one kind of change no offline check can verify and which
  costs a paid run to fix and a second to confirm. Deferred deliberately, four days from
  submission, rather than attempted and left unverified.
- **Sessions are bounded, not revocable.** They are signed cookies, so signing out
  deletes the browser's copy and a stolen one stays valid until its fourteen days are up.
  Revoking on demand needs a server-side session table.
- **One research entry stays pending.** Its containing volume is confirmed; nothing found
  places the chapter in it. Promoting it to round the number up would be the most
  corrosive thing anyone could do to that layer.
- **`proposed_by` cannot distinguish fixture from agent.** The column allows `'agent'` or
  `'user'`, so hand-written demo evidence is stored as `'agent'`. The character files
  distinguish them; the database does not. Fixing it is a schema bump.
- **No migrations.** A schema change requires deleting the database and re-seeding, and
  `Store()` refuses to open a stale one rather than failing later. Right trade with no
  real users; needs Alembic before anybody's journal depends on it.
- **A hosted free instance is not durable storage**, and since 2026-11-18 the *app* says
  so — on the sign-up screen above the first field, in Settings beside the export button,
  and on `/api/health` — rather than only the README. `backend/durability.py` holds the
  flag and the sentence; the container image defaults to "keeps nothing", so a deployment
  must opt in to claiming durability after mounting a real disk. Before that the fact was
  written in three files and said to nobody who was about to type into it, which is an app
  accepting a relationship journal it knew it could not keep.
