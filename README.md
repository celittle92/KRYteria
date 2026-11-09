# KRYteria

**Knowledge. Relationships. You.** · *Personal decision intelligence, powered by AI.*

> Relationships are complicated. Standards are not.

KRYteria is a decision mirror. It helps a person compare three things: what they say they
want, what they are actually experiencing, and what they are choosing to do about it.

It is **not** a dating app, a compatibility score, a red-flag detector, a breakup adviser,
or a chatbot that agrees with you. The product insight is that people are usually not
short of information — they struggle to act consistently with information they already
hold.

> **You have the information. How are you acting on it?**

MGT 409 final project · Christine Little · Yale SOM

---

## Status

**Backend and agents are built. The web interface is not yet.** This is an in-progress
repository, not a finished submission. What works today is verifiable from the test
suites and the Python API; there is no browser UI to open yet.

| Piece | State |
|---|---|
| Data model (33 tables) | built, 203 checks |
| Agent output contracts | built, 94 checks |
| Seven agents + orchestrator | built, 74 wiring checks |
| Deterministic demo mode (no API key) | built |
| HTTP API | built, 129 checks |
| Privacy architecture | built — isolation, retention, redaction |
| Synthetic demo account | built, runs with no API key |
| Front end | not started |
| `report.html`, `slides.html` | not started |

**476 checks in total**, none of which call a model.

---

## Running it

Requires Python 3.12+ (developed on 3.14.7). No database server, no external services.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### Start it

```bash
.venv/bin/python -m backend.seed_demo
```

```bash
.venv/bin/python -m uvicorn backend.main:app --port 8000
```

Then open **http://localhost:8000/api/health** — it reports the mode, the model, whether a
key was found and *where it looked*, and whether prices are loaded. Interactive API docs
are at **/docs**.

There is no browser interface yet, so `/` returns a short JSON status rather than a page.

The demo account is `demo` / `kryteria-demo-account`. Everything in it is invented.

### The research knowledge base

KRYteria can suggest behavioural indicators informed by published research — but only
from a curated set somebody has checked. **A citation must resolve to a verified entry**,
so the agent cannot invent a reference: `research_ref` is matched against the knowledge
base and anything else is rejected.

19 findings are drafted and **none is verified yet**, so the agents currently cite
nothing and mark every suggestion as their own hypothesis. To verify them:

```bash
.venv/bin/python -m backend.verify_research list
```

`show <ref>` prints an entry with what to check; `ok <ref> --url <what you opened> --by
<name>` promotes it, and refuses without a URL.

### Tests — free, no API key, no network

```bash
python3 tests/test_offline.py
```

```bash
.venv/bin/python tests/test_contracts.py
```

```bash
PYDANTIC_AI_NO_BANNER=1 .venv/bin/python tests/test_wiring.py
```

```bash
PYDANTIC_AI_NO_BANNER=1 .venv/bin/python tests/test_api.py
```

476 checks in total. The first needs no installed packages at all — it stubs the password
hasher so the data layer can be verified on a bare Python. The last runs the whole HTTP
layer in demo mode, and its most important test is two accounts trying to reach each
other's rows every way the API allows.

### Where KRYteria looks for an API key

In this order:

1. `.env` in this folder
2. `.env` in the folder **above** this one
3. the process environment

The second case is deliberate: MGT 409 submissions are cloned side by side under one
folder with a single shared `.env` one level up. That layout is supported and tested.

Copy `.env.example` to `.env` and fill in `PORTKEY_API_KEY`. The model is pinned to
`gpt-6-luna`, the only model the course key permits — `OPENAI_MODEL` is read but cannot
override it, and an ignored value is reported rather than silently substituted.

### Demo mode needs no key at all

With no key reachable, KRYteria falls back to a deterministic provider that returns fixed,
plausible, clearly-labelled responses. The whole journey runs: a fresh clone with no
`.env` works rather than crashing on import.

```bash
KRYTERIA_MODE=demo .venv/bin/python -c "
from backend.provider import build
model, info = build()
print(info)
"
```

Everything demo mode produces is flagged `is_simulated` and is excluded from every token
and cost figure, so a demo can never contaminate a measured number.

---

## How it works

Seven modules. Six are model-backed agents; the orchestrator routes between them and
spends no model call of its own deciding how to route.

```
        User brain dump — narrative + selected person + selected profile
                              ↓
                       Orchestrator
                              ↓
        ┌─────────────────────┴─────────────────────┐
     Narrative Agent                          Safety Layer
     observations, feelings,                  potential abuse, coercion,
     interpretations, uncertainty             immediate safety concerns
        └─────────────────────┬─────────────────────┘
        ┌─────────────────────┴─────────────────────┐
     Evidence Agent                           Reasoning Agent
     maps observations to                     interrogates assumptions,
     profile-specific criteria                cross-criterion trade-offs
        └─────────────────────┬─────────────────────┘
                              ↓
                   Validation + User Review
                              ↓
                     KRYteria Reflection
```

A seventh agent, Criteria, serves the criteria screen and Checklist Mode and sits off the
brain-dump path entirely.

Full detail in [`docs/architecture.md`](docs/architecture.md).

### The three-level model

1. **Master criteria library** — reusable personal standards. No tier, no profile.
2. **KRYteria Profiles** — independent configurations that select criteria from the
   library and assign *this profile's* importance tier and relevance.
3. **Assessments** — evidence about one person, judged against **one selected profile**.

The same person assessed under two profiles has two independent answers, and neither
contradicts the other. Changing a tier in one profile never reaches into another.

### Four assessment statuses

`pass` · `unknown` · `fail` · `not_applicable`

`unknown` is the default and an honest result, not an empty state. `not_applicable` is
never treated as pass, fail, or missing information.

---

## What the code enforces, rather than asks for

A prompt is a request; a journal entry can argue with one. These are validators and
database constraints:

- **No numeric score** for a person or a relationship exists anywhere — no column, and any
  agent output containing one is rejected.
- **No agent can change an assessment status.** Agents write to a proposals table; only
  the user's own action moves a status, and every transition is recorded with its previous
  value, origin and explanation.
- **A pattern must name the entries it rests on.** Below three supporting entries it is
  forced to `insufficient`, whatever the model claimed, and the counts are computed from
  the entries actually supplied rather than trusted.
- **A confident finding must offer an alternative explanation**, or it is rejected. A
  finding that admits no other reading is a verdict.
- **Counter-evidence is stored beside supporting evidence**, as a first-class row.
- **An inferred observation must carry a hedge** that invites correction, so a reading is
  never presented as something the user said.
- **Criteria are versioned, never overwritten** — how somebody's standards changed over
  time is among the most useful things this app can show them.
- **The safety layer is independent of profiles.** It takes no profile argument, and a
  test asserts it never gains one.
- **Unreported cached-token counts are stored as unknown, not zero.**

---

## Safety

KRYteria is not therapy, a medical or legal service, or a crisis line, and it says so.

The safety layer runs on the raw narrative alongside the Narrative agent — never
downstream of a mapping, never gated on the selected profile. A user never has to list
physical safety, consent, or freedom from coercion as a criterion before a concern is
recognised.

**Support without coercion.** Resources are offered, never forced. A decline is respected
and not re-raised. Declining turns off unsolicited offering, **not** the safety layer:
immediate danger always surfaces emergency options regardless of preference or prior
decline.

Over-responding is treated as a failure in its own right. Producing a crisis line because
a sensitive word appeared, when the person was describing an ordinary evening, is graded
against in [`tests/evals/safety_evals.json`](tests/evals/safety_evals.json) exactly as
minimisation is.

KRYteria may say *"that behaviour may be a form of coercive control."* It may never say
*"he is an abuser."*

> ⚠️ The support resources in `data/resources_us.json` have **not yet been independently
> verified** against each organisation's published contact details. Do not rely on them
> until they have been.

---

## Privacy

> **KRYteria is a private space between a person and their AI agent. No other person can
> know whether they have been discussed, assessed, or entered into KRYteria.**

Full detail in [`docs/privacy.md`](docs/privacy.md). The short version:

**Nothing can signal anybody.** There is no sharing, no collaborative assessment, no
partner invitation, and no "you've been mentioned" mechanism of any kind. No API route
accepts another user's identifier — every route resolves the account from a signed
session cookie, so a route *cannot* be pointed at somebody else's rows. Being mentioned
here is indistinguishable, to the person mentioned, from never having been mentioned.

**You decide what is kept.** Three retention modes, set once and overridable per entry:

| | |
|---|---|
| `discard` | the narrative **and everything derived from it** are erased |
| `analysis_only` *(default)* | the narrative is erased; observations and mappings survive |
| `keep_all` | everything stays until you delete it |

Erasure overwrites the text with `NULL` and runs in the same request as processing. The
default keeps the analysis and not the original, because keeping the most sensitive thing
in the product should not require an opt-out.

**Telemetry carries no private writing.** The execution log holds tool names, token
counts, latency and model versions — never argument values. Error messages are redacted
before storage, because a validation error embeds the value that failed it.

**What we do not control:** the model provider received your reflection in order to
process it. Our erasure governs our database, not theirs. Their retention policy is
**not yet established**, so KRYteria does not claim your data is never retained anywhere.
See `docs/privacy.md` §5.

### The rest

- Accounts are **anonymous** — a handle of your choosing, no email, no name.
- Passphrases are hashed with **Argon2id** (`pwdlib`). Never stored, returned, logged or
  rendered in any form.
- People in your journal are stored as **aliases only**. There is no column for a real
  name.
- Export and delete-everything are both supported, and deletion removes rows rather than
  flagging them.
- The API key stays server-side. The browser never calls the model provider.
- **Raw journal text never enters telemetry.** The execution log records tool names and
  argument keys, never argument values — it is shown on screen and pasted into reports.

Data is stored in a local SQLite file. That is **not** production-grade encryption and
this project does not claim otherwise.

---

## Repository layout

```
backend/
  schema.sql          33 tables; the comments explain the non-obvious constraints
  store.py            every agent tool reaches the database through here
  models.py           Pydantic output contracts for every agent
  security.py         Argon2id
  provider.py         model-provider abstraction: live / demo / test
  demo_provider.py    deterministic, keyless; a product mode, not a test double
  costs.py            measured token accounting
  agents/             seven modules, one per agent
  prompts/            seven runtime prompts, loaded from disk on every call
data/
  resources_us.json   curated support directory (unverified — see above)
  prices.json         per-million-token prices (not yet filled in)
docs/architecture.md
tests/
  test_offline.py     store layer, no dependencies needed
  test_contracts.py   agent output contracts
  test_wiring.py      hashing, provider, agent construction, budget caps
  evals/              adversarial reasoning and safety scenarios
```

No prompt is inlined as a string literal in Python. Every agent names its prompt file and
reads it at runtime.

---

## Cost control

A hosted app spends money when strangers use it, so the limits are in code, not in a
prompt asking a model to be frugal:

- Per-account and global **daily token caps**, checked before a run starts.
- **Hard ceiling of five model calls** per request. No loops.
- The orchestrator routes to the **minimum**: three calls for an ordinary entry, four when
  there is a generalisation to interrogate, five only when reflection is wanted.
- Retrieval is always a tool call, never a model call.

`data/prices.json` has no prices yet, so `estimate_cost` returns `0.0` and the app reports
cost as *unavailable* rather than printing a zero as though a run were free.

---

## Known limitations

- No web interface yet; no `report.html` or `slides.html`.
- **No live model call has ever been made from this project.** Everything is verified
  against `TestModel` and the deterministic demo provider.
- Support resources and model prices are both unverified placeholders.
- The research knowledge base is drafted but unverified, so no agent cites it yet.
- No database migrations. A schema change means deleting the database and re-seeding;
  the store refuses to open a stale one and says exactly how to fix it.
- Single-region (US) resource directory.
- Tough Love communication mode is specified but deliberately not built.
