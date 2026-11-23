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

## ▸ Open it here: **<https://kryteria.onrender.com>**

Press **See it working** — it opens a finished journal, no sign-up and nothing to type.
Nine more demonstration people are inside it under **Other scenarios**. **A free instance
sleeps after about fifteen minutes, so the first load can take a minute.** That is the host
waking up, not a broken link. If the link is asleep or you would rather run it yourself,
[Running it](#running-it) below is tested from a fresh clone and needs no API key.

---

## A note on the deck

`slides.html` is **not built on reveal.js**, which the requirements page suggests. It is
ten `<section>` elements and about twenty lines of JavaScript, and it meets every
behaviour the page actually specifies: ten slides, arrow keys and space to navigate,
**F** for full screen, screenshots and the agent diagram embedded in the file.

The reason is the requirement one paragraph above it: both HTML files must *"open by
double-clicking, on any computer, with every screenshot showing."* reveal.js loaded from
a CDN needs a network at the moment it is opened. A grader on a plane, behind a proxy, or
on a locked-down machine gets a blank page — and a deck that fails to open is worth less
than one built the unfashionable way. `slides.html` has **zero external scripts** and
every image inlined as a data URI, so it opens from a USB stick with the wi-fi off.

Stated here rather than hoped past.

## Status

**Complete and deployed.** Backend, seven agents, front end, demo data, report and deck.

| Piece | State |
|---|---|
| Data model | built, 601 checks |
| Agent output contracts | built, 224 checks |
| Seven agents + orchestrator | built, 74 wiring checks |
| HTTP API, incl. cross-account isolation | built, 345 checks |
| Evaluation harness | built, 387 checks |
| Deterministic demo mode (no API key) | built |
| Privacy architecture | built — isolation, retention, redaction |
| Front end (React + Vite + TS) | built, `dist/` committed so no Node is needed |
| Nine-character demo | built, analysis frozen from live runs |
| Hosted deployment | live at kryteria.onrender.com |
| `report.html`, `slides.html` | built, self-contained |

**1,631 checks across 169 test functions**, five suites, none of which call a model.
Measured live model spend to date: **$0.248** over 404 calls across 22 runs. Three of those runs lack a cost figure and are excluded rather than estimated, so the real figure is a little higher.

---

## Running it

No database server, no external services, no Node. **Four commands and a browser.**

**First, check your Python.** This needs **3.12 or newer**, and macOS ships 3.9 as
`python3` — which is the one thing most likely to cost you ten minutes here.

```bash
python3 -V
```

If that prints 3.12 or higher, use `python3` below. If it prints 3.9 or 3.11, look for a
newer one and use that name instead (`python3.12`, `python3.13`…):

```bash
ls /opt/homebrew/bin/python3.1* /usr/local/bin/python3.1* 2>/dev/null || brew install python@3.12
```

The app checks this itself on first import and refuses with the same advice rather than
failing somewhere confusing later. If you would rather not think about it,
[Deploying it](#deploying-it) builds a Docker image that pins the interpreter, and
<https://kryteria.onrender.com> needs nothing at all.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### Start it

Build the demo data. **Both commands** — the first makes the single `demo` account, the
second makes the nine demonstration people, including the one **See it working** opens.
Running only the first leaves that button on a 404.

```bash
.venv/bin/python -m backend.seed_demo && .venv/bin/python -m backend.seed_characters
```

Then start it. One process serves the API and the interface, so there is one thing to run
and one port:

```bash
.venv/bin/python -m uvicorn backend.main:app --port 8000
```

Open **<http://localhost:8000>** and click a character. Nothing to type.

**<http://localhost:8000/api/health>** reports the mode, the model, whether a key was
found and *where it looked*, and whether prices are loaded. Interactive API docs are at
**/docs**. `frontend/dist` is committed, so no Node is needed; if it were missing, `/`
returns a JSON status explaining how to build it rather than a bare 404.

### The demo: nine people, nothing to type

The sign-in screen lists nine demo characters and opens one in a click — no sign-up, no
handle, no passphrase. They are built on first boot and rebuilt by
`POST /api/demo/reset`, or from the command line:

```bash
.venv/bin/python -m backend.seed_characters --reset
```

To sign in by hand, the passphrase is `kryteria-demo-` followed by the handle
(Catherine is `thelonggame` / `kryteria-demo-thelonggame`).

| | handle | |
|---|---|---|
| Jane | `theintentionalist` | the postponement loop, and a standard that quietly got easier |
| Bianca | `notyourtherapist` | counter-evidence against a conclusion she likes |
| Vanessa | `afterhours` | two profiles for one person; `not_applicable`; the safety case |
| Catherine | `thelonggame` | cross-criterion reasoning, soft hands, the shared evening |
| Adrian | `theproducer` | the same evening, read differently |
| Joe | `thequietone` | a thin record producing honest Unknowns |
| Will | `thewildcard` | disclosure and accountability as separate facts |
| Jack | `thegoodone` | insufficient evidence preserved rather than filled in |
| Greg | `theunderdog` | circumstances and character as different questions |

Every person, entry and assessment is invented. **Catherine and Adrian describe the same
Thursday evening in separate private accounts** — neither can see the other, and KRYteria
never tells either of them that somebody else wrote about that night. Open both.

The analysis in the proof-point entries is real agent output from a live run, frozen into
`data/characters/*.json` by `backend/run_character_analysis.py` so the hosted app shows it
without spending credits on every restart. Everything a model produced sits under a
`generated` key; everything else was written by a person.

### The research knowledge base

KRYteria can suggest behavioral indicators informed by published research — but only
from a curated set somebody has checked. **A citation must resolve to a verified entry**,
so the agent cannot invent a reference: `research_ref` is matched against the knowledge
base and anything else is rejected.

**Sources must be reputable, and that is enforced rather than promised.**
`backend/sources.py` accepts `.gov` and `.edu` domains, academic country domains matching
`.ac.<cc>` / `.edu.<cc>`, scholarly publishers, permanent identifiers such as `doi.org`
and PubMed, and library catalogs. It refuses encyclopedias, popular-psychology sites,
upload sites, blogs, retailers and wellness brands — by allowlist, so a source nobody
thought of is refused rather than admitted. `academia.edu` is explicitly refused: the
`.edu` belongs to the company, not a university.

**18 of 19 entries are verified and citable** (17 reach the criteria and evidence agents;
`stark-coercive-control` is safety-adjacent and withheld from them). One stays pending —
`reis-shaver-responsiveness`, where the containing handbook is confirmed but nothing found
shows the chapter is in that volume or at what pages. It records exactly that. To work
through it:

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

```bash
PYDANTIC_AI_NO_BANNER=1 .venv/bin/python tests/test_evals.py
```

1,631 checks in total. The first needs no installed packages at all — it stubs the password
hasher so the data layer can be verified on a bare Python. `test_api` runs the whole HTTP
layer in demo mode, and its most important test is two accounts trying to reach each
other's rows every way the API allows.

### Evaluations, and the A/B against a general-purpose chatbot

36 adversarial cases — 18 on safety, graded in **both** failure directions, and 18 on
reasoning quality — plus a head-to-head against the way this is done today.

```bash
PYDANTIC_AI_NO_BANNER=1 .venv/bin/python -m backend.run_evals list
```

```bash
PYDANTIC_AI_NO_BANNER=1 .venv/bin/python -m backend.run_evals all
```

That second command is free: it runs in demo mode, which proves the harness executes and
grades **nothing** about the real agents. Its output goes to `output/demo_runs/` and every
page says so on the first line. Real results need `--mode live --yes-spend-credits`, which
prints the call count before it starts.

Of the 145 checks, 108 run automatically and **37 are marked `manual`** — requirements like
"acknowledge what happened without judgment" that no honest predicate can settle. They are
listed as a checklist for a person and are never counted as passes. An LLM judge would
have automated them, and would have been this project's own model grading its own output
against its own rubric; that trade is explained in `backend/evals/checks.py`.

The A/B grades both systems **on prose only**. Scoring KRYteria on the structure it emits
and a chatbot on prose it cannot structure would measure the output format rather than the
thinking. What only one system produced at all is reported separately as capability. The
baseline runs on the same model with a deliberately fair prompt
(`backend/prompts/baseline_chatbot.md`).

### Where KRYteria looks for an API key

In this order:

1. `.env` in this folder
2. `.env` in the folder **above** this one
3. the process environment

The second case is deliberate: MGT 409 submissions are cloned side by side under one
folder with a single shared `.env` one level up. That layout is supported and tested.

> **An environment variable that is already set beats both files.** `load_dotenv` never
> overwrites one. So if your shell exports `PORTKEY_API_KEY` — from `~/.zshrc`, say — the
> app uses that and silently ignores whatever you put in `.env`. This cost an hour on
> 2026-11-20: a rotated key was updated correctly in `.env` and on the host, while five
> stale `export` lines in `~/.zshrc` kept handing every local command the dead one.
> `/api/health` reports `env_source` and the last four characters of the key it loaded,
> which is the fastest way to tell which copy you are actually running on.

Copy `.env.example` to `.env` and fill in `PORTKEY_API_KEY`. The model is pinned to
`gpt-6-luna`, the only model the course key permits — `OPENAI_MODEL` is read but cannot
override it, and an ignored value is reported rather than silently substituted.

### Demo mode needs no key at all

With no key reachable, KRYteria falls back to a deterministic provider that returns fixed,
plausible, clearly-labeled responses. The whole journey runs: a fresh clone with no
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

### Deploying it

One image, one process, one port. The app serves its own built front end, so there is no
second service, no reverse proxy and no CORS to configure.

```bash
docker build -t kryteria . && docker run -p 8000:8000 -e KRYTERIA_MODE=demo kryteria
```

The `Dockerfile` pins the interpreter rather than accepting a platform default. This
project is developed on Python 3.14 and most hosts still default to 3.11 or 3.12; an image
removes the question entirely. `render.yaml` is a ready blueprint for a free Render web
service and documents each variable's reasoning.

| Variable | What it does |
|---|---|
| `PORTKEY_API_KEY` | The model key. Supplied by the host as an environment variable, never committed or baked into an image layer. |
| `PORT` | Assigned by the host; the container honors it. |
| `KRYTERIA_HOST` | Bind address. `0.0.0.0` in a container, `127.0.0.1` on a laptop. |
| `KRYTERIA_DB_PATH` | Where the SQLite file lives. Set it outside the source tree so a redeploy cannot replace somebody's journal. |
| `KRYTERIA_SECRET_KEY` | Signs the session cookie. **Set this in production** — the development fallback generates one per process, which would sign everybody out on every deploy. |
| `KRYTERIA_SECURE_COOKIES` | `true` over https, so the session cookie refuses to travel in clear text. |
| `KRYTERIA_SEED_ON_BOOT` | Rebuild the synthetic demo account at startup. See below. |
| `KRYTERIA_MODE` | `demo` to run free and simulated; otherwise live whenever a key is reachable. |

**Two things about free hosting, stated plainly rather than discovered later.**

A free instance **sleeps** after roughly fifteen minutes of inactivity and takes about a
minute to wake. The first request after a quiet spell will be slow. That is expected, not
a broken link — and it is exactly why the local instructions above are tested and kept
current. The hosted link is the front door; the local path is what works when the front
door is asleep.

A free instance also has an **ephemeral disk**. The SQLite file does not survive a restart
or a redeploy. `KRYTERIA_SEED_ON_BOOT=true` turns that from data loss into a self-healing
demo: the synthetic account is rebuilt on every boot, so the demo is always there however
often the host recycles the process. It is idempotent and only ever touches the synthetic
account.

**The app says this itself, on the screen where it matters.** `KRYTERIA_STORAGE_DURABLE`
(`backend/durability.py`) tells KRYteria whether its disk survives a restart, and when it
does not, the sign-up screen carries the notice **above the first field** and Settings
repeats it beside the export button. The default for the container image is `false`, so a
deployment has to opt *in* to claiming durability after actually mounting a disk —
defaulting the other way makes the app promise durability by omission on every host that
has none. `/api/health` reports both the flag and the sentence. This was added after the
limitation had been documented in `render.yaml`, the `Dockerfile` and this file, and said
to nobody who was about to type into it.

**Anything a real visitor writes is lost when the instance restarts.** This is a class
demonstration deployment and it should not be mistaken for durable storage. Attaching a
persistent disk at `/data` is the upgrade path, and the `Dockerfile` already puts the
database there.

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

Full detail in §4 of `report.html`. [`docs/architecture.md`](docs/architecture.md) is the **frozen Milestone-1 plan** from before any of it was built, kept unedited as a record of what was intended — useful beside the result, misleading on its own.

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
recognized.

**Support without coercion.** Resources are offered, never forced. A decline is respected
and not re-raised. Declining turns off unsolicited offering, **not** the safety layer:
immediate danger always surfaces emergency options regardless of preference or prior
decline.

Over-responding is treated as a failure in its own right. Producing a crisis line because
a sensitive word appeared, when the person was describing an ordinary evening, is graded
against in [`tests/evals/safety_evals.json`](tests/evals/safety_evals.json) exactly as
minimization is.

KRYteria may say *"that behavior may be a form of coercive control."* It may never say
*"he is an abuser."*

> All five US entries in `data/resources_us.json` were checked against each
> organization's own site, and each row shows its `verified_at` date **on screen** — a
> dated number can be judged; a bare one asks for trust nobody earned. Two of them
> (RAINN, 911) refuse automated fetching and were confirmed by a person opening them on
> 2026-11-16. `data/resources_international.json` holds nine more across five countries
> plus EU-wide 112. The directory is deliberately **small and not comprehensive** — see
> `docs/safety_resources_decision.md` for why, and for the three services excluded with
> their reasons recorded.

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
- **A recovery code is issued once at sign-up**, and it is the way back in if the
  passphrase is forgotten. Six words, hashed with Argon2id like a passphrase — because
  anything that can reset a passphrase can open the journal, so it is a credential and
  not a hint. The plaintext is in that one response and nowhere else: it is not stored
  readably, cannot be shown again, and nobody operating this app can look it up.
  Using it consumes it and a fresh one is issued, so a code written on paper does not
  stay live after a reset.

  The alternative was an email address, and it was rejected deliberately. An email is a
  real identity on file and a notification channel visible to anyone with access to that
  inbox — which is precisely the exposure a relationship journal has to design around,
  and the same reasoning that keeps `accounts.region` user-set and never inferred. A
  code the user writes down fixes the recovery problem and adds neither. The cost is
  real and is stated at sign-up: lose both the passphrase and the code and the account
  cannot be opened by anyone.
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
  main.py             one process serves the API and the built front end
  schema.sql          34 tables; the comments explain the non-obvious constraints
  store.py            every agent tool reaches the database through here
  models.py           Pydantic output contracts for every agent
  security.py         Argon2id passphrases and recovery codes
  security_headers.py CSP, frame-ancestors 'none', HSTS only over https
  throttle.py         brute-force protection keyed per handle, plus a keyless bound on
                      how fast the app as a whole will create accounts
  provider.py         model-provider abstraction: live / demo / test
  demo_provider.py    deterministic, keyless; a product mode, not a test double
  costs.py            measured token accounting
  sources.py          the allowlist a research citation must come from
  seed_demo.py        the single `demo` account
  seed_characters.py  the nine demo characters, from data/characters/
  agents/             seven modules, one per agent, plus the orchestrator
  api/                the HTTP routes, each scoped by account
  evals/              the harness that runs the adversarial packs
  prompts/            eight runtime prompts (seven agents + the A/B baseline)
frontend/
  src/                React + Vite + TypeScript; six in the navigation,
                      plus /checklist and /reflection by route
  dist/               built, and committed on purpose — a grader needs no Node
data/
  characters/         nine demo accounts, analysis frozen from live runs
  resources_us.json   curated support directory, each row dated and verified
  resources_international.json   ten more across five countries, plus EU-wide 112
  research/           the curated knowledge base; a citation must resolve into it
  prices.json         per-million-token prices for gpt-6-luna, from the course figures
  themes.json         the closed theme vocabulary
docs/
  privacy.md          the privacy architecture, and what it does NOT promise
  architecture.md     the frozen Milestone-1 plan, kept unedited
  safety_resources_decision.md   why the directory is small and dated
tests/
  test_offline.py     store layer, runs on a bare Python with nothing installed
  test_contracts.py   agent output contracts
  test_wiring.py      hashing, provider, agent construction, budget caps
  test_api.py         the HTTP layer, including isolation between accounts
  test_evals.py       the eval harness — mostly that it refuses rather than skips
  evals/              the adversarial reasoning and safety packs
tools/
  check_consistency.py   every number in the docs, checked against the source
  fresh_clone_check.sh   the dry run: clone, .env one level up, follow the README
  trace_one.py           run one entry live and print the per-agent trace
  screenshots.sh         regenerate the report's screenshots
output/                report.html and slides.html evidence: usage, evals, screenshots
report.html            the submitted report, self-contained
slides.html            the submitted deck, self-contained
```

No prompt is inlined as a string literal in Python. Every agent names its prompt file and
reads it at runtime.

---

## Cost control

A hosted app spends money when strangers use it, so the limits are in code, not in a
prompt asking a model to be frugal:

- Per-account and global **daily token caps**, checked before a run starts.
- **Hard ceiling of five model calls** per request. No loops.
- The orchestrator routes to the **minimum**: three calls for an entry that draws no
  conclusion, four when the writer stated one and Reasoning has something to interrogate
  (the common case, $0.00208), five only when reflection is wanted.
- Retrieval is always a tool call, never a model call.

`data/prices.json` carries the course's published figures for `gpt-6-luna` — $0.10
input, $0.01 cached input, $0.50 output per million tokens — so `estimate_cost` returns a
real number. For a model it has no prices for it still returns `0.0` and the app reports
cost as *unavailable* rather than printing a zero as though a run were free.

---

## Known limitations

- **No database migrations.** A schema change means deleting the database and
  re-seeding; the store refuses to open a stale one and says exactly how to fix it. This
  is acceptable with no real users and needs Alembic before anybody's journal depends
  on it.
- **A free instance is not durable storage.** Its disk is ephemeral, so anything a real
  visitor writes is lost on restart. The demo rebuilds itself on every boot, and the app
  states the limitation on the sign-up screen and in Settings rather than leaving it in
  this file. Making it durable needs a paid instance with a disk mounted at `/data`
  (`render.yaml` carries the commented block) and `KRYTERIA_STORAGE_DURABLE=true`.
- **Sessions are bounded, not revocable.** They are signed cookies, so signing out
  deletes the browser's copy and a stolen one stays valid until its fourteen days are up.
- **Cache writes are not modeled** in cost figures, because the provider does not report
  them separately, so figures are slightly low on a cold cache and correct once warm. The
  cached-input count itself *is* reported and captured — measured at zero across ten calls
  on two 17 November runs, which is what a cold cache should produce. Stated in the report
  rather than smoothed over.
- **37 of 145 evaluation checks need a human** and are marked `manual`. An LLM judge
  would have automated them and would have been this project's own model grading its own
  output against its own rubric.
- **One research entry of nineteen stays pending** — its containing volume is confirmed
  and the chapter's placement in it is not, so no agent may cite it.
- **The support directory is small on purpose**, not comprehensive.
- Date Calendar and Cooldown are designed and deliberately not built (P1).
- Tough Love communication mode is specified and deliberately not built (P2).
- SQLite on a host is not production-grade encryption, and this says so rather than
  implying otherwise.
