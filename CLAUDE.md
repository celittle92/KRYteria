# KRYteria project memory

Authoritative rules live in `.claude/rules/final-project-kryteria.md`, one level up in the
private AI Foundations workspace. The import below resolves only inside that workspace,
not in a standalone clone of this repo. Read that file, plus `AI_prompts.md` and
`docs/architecture.md`, before changing anything here.

@../.claude/rules/final-project-kryteria.md

## Local facts

- **This folder IS the repo.** Flat, unlike HW4–HW6 which nest a `hwN/`. The workspace
  root is one level up.
- **The venv exists** (built 2026-11-07, Python 3.14.7). Installed: pydantic-ai-slim
  2.66.0, pydantic 2.14.3, openai 3.46.0, fastapi 0.162.2, uvicorn 0.54.0, pwdlib 0.3.1
  with argon2-cffi 25.1.0, tiktoken 0.14.0, itsdangerous, python-dotenv.
  Rebuild from the **Terminal panel**, not sandboxed Bash — the sandbox blocks the
  certificate pip writes during `ensurepip`:

  ```bash
  cd "/Users/christinelittle/Yale SOM_Old/AI Foundations/KRYteria"
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  ```

- **`format_history` LABELS the current entry, it does not hide it.** Excluding it was
  an over-correction (2026-11-11) that cost real capability: the first live run found
  three occasions of a pattern, could cite only two, and fell below `MIN_SUPPORT`. The
  agent reported this itself in a `gap_note` — *"no entry ID for it is provided, so only
  two distinct entries can be cited here."* Today's entry is evidence of today; what it
  must not be is *prior* corroboration for the conclusion drawn from it, so it is listed
  with that warning attached. **Do not go back to excluding it.** Test in
  `test_contracts.py`.
  Re-run with the fix: `supporting=[2,4]`→`[2,4,12]`, `contradicting=[]`→`[5]`,
  strength `insufficient`→`moderate`.
- **A mis-diagnosis to learn from.** I first called the empty `contradicting_entry_ids` a
  failure to record counter-evidence. It was not: the agent's claim was deliberately
  narrow (*"not by itself a conclusion that he is unreliable in every area"*) and the
  counter-example did not contradict *that*. The symptom was real, the cause was
  elsewhere, and the system had said so in its own `gap_note`. **Read what the agent
  says about itself before diagnosing what it produced.**
- **Measured cost of a full brain dump: $0.00341** (5 agents incl. reflection, 9,109 in
  / 4,992 out). Reflection is opt-in, so the 4-agent $0.00208 is the common case. Total live spend to date:
  **$0.20001** measured across **15 runs**: 14 reported token counts and 13 reported a cost. The two without one are excluded from the total rather than estimated, so real spend is a little higher (`output/token_report.md`).
- **A safety halt withholds the ANALYSIS, it does not stop the RECORD** (Christine's
  call, 2026-11-12). On `disclosure` or `immediate_danger` — `WITHHOLD_ANALYSIS_AT`,
  checked in code, **not** read off `suggested_action` — Narrative, themes and Evidence
  still run and persist; Reasoning and Reflection are skipped; and the response carries
  `analysis_withheld` + `analysis_recorded` + a sentence telling her it was kept. Before
  this the orchestrator returned before `save_observations`, so her most serious entry
  was her least recorded one. **Never restore an early return there**; a test asserts
  the halt is set before the save.
- **Stalking and other escalating patterns always get a safety check.**
  `agents/safety.ALWAYS_CHECK_SAFETY` supplies the charter's question when the model
  omits it, tagged `policy:safety_check_supplied` in the trace. It **supplies rather
  than rejects** — a validation error would make the safety step fail, and a failed
  safety step means no safety output at all, i.e. failing open on the cases this layer
  exists for. The root cause was `safety.md` reserving the question for immediate
  danger; that section is rewritten and there is a regression test.
- **Support resources are matched to `accounts.region`, which the user sets and nothing
  infers.** ISO 3166-1 alpha-2 or NULL. **No IP lookup, no `X-Forwarded-For`, no
  timezone guess** — a test sends spoofed location headers and walks the AST of every
  route module to confirm nothing touches the request except `cookies`. `list_resources`
  no longer defaults to `"US"`; unset means `GLOBAL` rows only plus an honest note, and
  a country with nothing curated returns nothing and says so.
- **The resource directory is deliberately SMALL, DATED, and not comprehensive.**
  `data/resources_international.json` holds nine entries across five countries plus
  EU-wide 112, each with `source_url` and `verified_at` from 2026-11-12. The decision
  and its evidence are in `docs/safety_resources_decision.md`; that document is also the
  report's Limits section.
  - **`verified_at` is shown to the user.** A dated number can be judged; a bare one
    asks for trust nobody earned.
  - **`api/account.EMERGENCY_NOTE`** — *"If you are in immediate danger, call your local
    emergency number"* — is carried on every resources response and whenever the safety
    layer fires. It hard-codes no digits on purpose: it is the one safety line no file
    of ours can make stale. A test asserts it never gains one.
  - **Three services are excluded with recorded reasons** (13YARN contradicts itself
    about its own number; Rape Crisis England & Wales' site was down; WAVE is an
    advocacy office, not a crisis line). A test keeps them out until the reason is
    resolved. **Do not re-add one without resolving why it was excluded.**
  - **Never add an entry from memory**, and **re-verify before the demo and before
    submission**, updating `verified_at` when you do. A stale date is honest; a fresh
    date on an unchecked row is not.
  - **`data/resources_us.json` was re-verified 2026-11-12, with mixed results.**
    thehotline.org **confirmed** (phone, text wording, 24/7 all match). 988lifeline.org
    **confirmed with corrections** — hours are "24/7/365" and the page never prints
    "Text 988", it exposes an `sms:988` link only, so our old wording was ours not
    theirs. **rainn.org returned HTTP 403 on every URL**, and **fcc.gov and 911.gov both
    403'd**, so RAINN and 911 could NOT be re-verified. Those two keep their original
    `2026-11-07` date deliberately — back-dating them would be a lie and removing them
    would leave US users with no sexual-assault resource and no emergency entry. **The
    gap is provenance, not accuracy.** Open them in a browser and update the date; a
    human can do in two minutes what an automated fetch cannot do at all.
  - Added `Deaf Hotline (video phone)` 855-812-1001, surfaced during that check — the US
    set had no accessible route for Deaf callers.
- **`SCHEMA_VERSION` is `2026-11-13.1`.** (It was `2026-11-12.1` when `accounts.region`
  landed; the character demo moved it again.) Delete
  `data/kryteria.db`, re-seed, and re-run `verify_research load` — the pack carries the
  verifications now, so they come back.
- **The Safety agent deliberately has no tools and no research lookup.** It runs
  concurrently on the raw text and must stay fast; the behavioural taxonomy lives in its
  prompt. Giving it retrieval is a design change, not a convenience.
- Two live-run findings still need **your decision, not a fix** — the `saf-threat-01`
  category (the charter's table puts threats under coercive control, so the case may be
  wrong) and one unadjudicated `prose_lacks`. See `output/live_runs/README.md`.
- **Eval artefacts store the FULL prose** (`produced.prose`, `produced.attributed`). The
  Markdown truncates at 2,000 characters and once hid the sentence that tripped a
  `prose_lacks` check, leaving a real failure unadjudicable without paying for the run
  again. Evidence that cost money must be complete in the machine-readable file.
- **`output/report_notes.md` is the running evidence record for `report.html` and
  `slides.html`** (49 of the 100 points, five rows evidence-capped at half). **Update it
  as evidence appears, not at the end.** Its rule: nothing goes in that is not already
  true and locatable, every figure names its source file, and intentions live under
  *Still missing*. It is a working record, deliberately **not** in
  `submission_spec.json`.
- **Research verification lives in the committed pack, not only the database.**
  `verify_research ok` writes `verification_status` / `verified_at` / `verified_by` back
  into `data/research/*.json` (`verify_research.record_in_pack`). It did not until
  2026-11-11, and deleting `data/kryteria.db` for the `entry_themes` schema bump
  destroyed all 18 signatures — the one part of that knowledge base a human had signed.
  `load_research_pack` honours them and still applies the source gate on the way in, so
  a pack cannot approve its own work. There is a test that rebuilds from the file alone.
- **Profiles: rename + archive, never delete.** `PATCH /api/profiles/{id}` edits the
  label; `POST /api/profiles/{id}/archive?archived=` hides or restores. **Do not add a
  per-profile delete route** — nine tables reference a profile, most cascading, and it
  holds the assessments made under it. A test asserts the route does not exist. Account
  deletion remains the way to erase.
- **Defaults: `frontend/src/choice.ts` is the single statement of the rule.** Exactly one
  profile/person → select it; more than one → select nothing and make the first option a
  **question**. A default is a soft recommendation, and "no profile ranks above another"
  means the UI must not imply one is the normal case. Used by BrainDump, QuickLog and
  Checklist. **The person is never inferred from the text** — names collide, and a
  misattribution files evidence against the wrong record silently.
- **Checklist Mode has a UI**: `frontend/src/screens/Checklist.tsx`, route `/checklist`.
  Generate indicators from a criterion (one model call, off the brain-dump path), then
  record observations in four states. **Ticking never moves a status**, and
  `no_opportunity` is deliberately distinct from `not_observed` — both facts are stated
  on screen, not just enforced in the store.
- **Themes (Intimacy & Relationship Experience Mapping), added 2026-11-11.**
  `data/themes.json` is a **closed** vocabulary of 10 topics; `backend/themes.py` loads
  and validates it; `NarrativeOutput.themes` and `store.save_themes` both reject an
  unknown id. The narrative prompt's `{{THEME_VOCABULARY}}` placeholder is filled from
  the file at build time, so the list the model sees and the list the store enforces
  cannot drift. Reachable at `GET /api/themes` and under `themes` on `/api/progress`.
  - **`entry_themes` has no status/score/relation column and must never gain one** — a
    theme says a subject came up, not that anybody did well at it. There is a test.
  - **`boundaries-and-consent` is a topic, not an alarm.** The Safety Layer does not read
    themes, is not gated on them, and runs concurrently on the raw text as before.
  - `sensitive: true` governs **presentation only** (no notification previews), never
    whether a theme is recognised.
  - Themes are deleted by `discard` and survive `analysis_only`, like observations.
  - **Seeded in the demo and rendered on My Progress** ("What you keep coming back to").
    Counts and dates only — never a score, and the copy says so.
- **`SCHEMA_VERSION` was `2026-11-11.1`** when `entry_themes` landed; it is
  `2026-11-13.1` now. An existing
  `data/kryteria.db` will be refused until it is deleted and re-seeded.

- **The eval harness runs the two packs that nobody could run before 2026-11-11.**
  `backend/evals/`, driven by `python -m backend.run_evals {list,safety,reasoning,ab,all}`.

  ```bash
  cd "/Users/christinelittle/Yale SOM_Old/AI Foundations/KRYteria" && PYDANTIC_AI_NO_BANNER=1 .venv/bin/python -m backend.run_evals list
  ```

  - **Demo mode is the default and is free.** It proves the harness executes; it grades
    nothing about the real agents. **A demo run cannot write a submission artefact** —
    output is diverted to `output/demo_runs/`, because `check_submission.py` decides the
    Safety evidence is present by the existence of `output/safety_results.json`, and a
    banner is no use when the reader is a script. `tests/test_evals.py` holds that line.
  - **Live mode is the only mode whose results are evidence**, and it refuses to start
    without `--yes-spend-credits` after printing the call count. **A full live run is
    about 149 model calls** — ask Christine first, and prefer `--only` with a handful of
    case ids.
  - Each case gets its **own account** in a throwaway database, so one case cannot see
    another's entries.
  - 95 automatic checks across 31 cases; **33 are honestly marked `manual`** and are
    never counted as passes. Do not "improve" that number by inventing a predicate for a
    prose requirement, and **do not add an LLM judge** — it would be our model grading
    our product against our rubric. That trade is recorded in `backend/evals/checks.py`.
  - **A/B dimensions must be answerable from prose by both systems**, enforced at load
    time. Grading KRYteria on structure and the chatbot on prose measures the output
    format, not the thinking. Structural differences are reported as *capability*,
    beside the score and never inside it.
  - `backend/prompts/baseline_chatbot.md` is deliberately a **good** generic prompt. A
    strawman baseline makes the whole comparison worthless; a test asserts it is not
    secretly handed the user's criteria.
  - **Known unsatisfiable case:** `inj-01` asks for a `safety_events` row recording a
    prompt-injection attempt, but `models.SafetyCategory` has no injection value. Decide
    it deliberately — add a category, or change the case — rather than dropping it.
  - **A `prose_lacks` needle must never be a phrase that appears inside its own denial.**
    "he is financially independent" fires on *"does not establish whether he is
    financially independent"*. Substring matching cannot see negation, and that limit is
    documented in `checks.py` rather than papered over.
  - **`prose_lacks` scans a system's own voice only.** `Transcript.attributed` holds what
    the agents explicitly marked as the user's — her conclusions, `interpretation`
    observations, interrogation `claim`s. Treating those as assertions scores the product
    down for the one thing it is built to do. There is a regression test with the
    verbatim string that caught this.

- **Reasoning routes on STATED CONCLUSIONS, not keywords** (fixed 2026-11-11, Christine's
  call). `needs_interrogation` returns True when the Narrative agent extracted any
  `user_conclusions`; the `GENERALISING` keyword list survives only as a fallback for a
  thin narrative result, and can add runs but never suppress one.
  **Why:** the first live A/B found the product's most load-bearing claim absent, and the
  cause was here. *"He's completely unreliable. I can't count on him for anything."*
  matches none of the 18 keywords, so Reasoning was skipped and the three contradicting
  entries were never sent to any model. Measured across the 36-text eval corpus, the old
  rule fired **4 times**, and **only 3 of the 13 adversarial reasoning cases ever reached
  the agent they were written to test.**
  **Do not re-introduce a keyword gate here.** A hand-written list of generalising words
  cannot gate the agent whose job is interrogating generalising claims; it catches the
  phrasings somebody thought of. There is a regression test carrying the verbatim
  sentence.
  **Cost, accepted deliberately:** Reasoning now runs on most entries containing an
  opinion. A brain dump goes **$0.00136 → $0.00208 (+53%)**; at 10,000 users and 12 dumps
  a month, **$162.88 → $249.62**.
- **`format_history` excludes the entry under analysis** (`current_entry_id`).
  `list_entries` returns it along with the rest, and presenting today's claim as an
  *earlier* entry lets a conclusion corroborate itself. Latent until the routing fix made
  the agent actually run.
- **`prose_lacks` ignores denials and claim-naming frames.** A match inside *"does not
  establish whether…"*, *"nothing here shows…"* or *"supports the conclusion that…"* is
  not an assertion. This replaced needle-patching after one bad needle turned out to have
  four siblings in scenarios that had not run yet — five instances of one bug means the
  bug is in the check. `transcript._is_negated` holds the cue lists; **do not add a cue
  that could excuse a real assertion** (`suggests that` and `evidence that` are
  deliberately absent), and
  `test_negation_handling_does_not_make_prose_lacks_toothless` guards that line.
- **Two live runs are archived in `output/live_runs/`, both with their real token counts
  and costs.** The 2026-11-11 **after-routing-fix** run is the one to quote: 12 calls,
  16,148 / 4,451 tokens, **$0.0038**, and it is where the product's central claim is
  actually demonstrated — KRYteria cited all three counter-entries and `Earlier entry
  [1]` by id, with `traceable_to_entry_ids` going False → True. **Its recorded scores
  (5–3, 3–4) predate the negation fix; the re-grade of the same stored text is 5–3 and
  4–4, and the README gives both.** The **first-live-run** file predates three fixes —
  do not quote its scores at all.
- **`output/live_runs/` is the archive of real runs and must not be overwritten.** A
  re-run writes `output/ab_comparison.*`; copy it in with a date before the next one.

- **Five test suites, all free, no API calls, no network:**

  | Suite | Interpreter | Covers |
  |---|---|---|
  | `tests/test_offline.py` | system `python3` | the store layer; stubs `backend.security` so it runs with nothing installed |
  | `tests/test_contracts.py` | `.venv/bin/python` | the Pydantic output contracts and the demo provider |
  | `tests/test_wiring.py` | `.venv/bin/python` | real Argon2id, provider resolution, agent construction on `TestModel`, budget enforcement |
  | `tests/test_api.py` | `.venv/bin/python` | the HTTP layer in demo mode, including **data isolation between accounts** and retention |
  | `tests/test_evals.py` | `.venv/bin/python` | the eval harness — mostly that it **refuses** rather than skips |

  1,521 checks across 157 test functions as of 2026-11-17, verified by `tools/check_consistency.py --tests`. Run all five after any change to `backend/`.

- **Run the app:** `.venv/bin/python -m uvicorn backend.main:app --port 8000`, then
  `/api/health` (needs no session) and `/docs`. Seed or reset the demo account first with
  `.venv/bin/python -m backend.seed_demo` — handle `demo`, passphrase
  `kryteria-demo-account`, all synthetic.
- **The running server defaults to LIVE mode on this machine**, because `app_config`
  finds `PORTKEY_API_KEY` in the workspace-root `.env` one level up. Verified 2026-11-07:
  `/api/health` reported `"mode":"live"` with `env_source` pointing at that file — which
  is exactly the staff `.env`-one-level-up case the assignment grades, confirmed in
  practice rather than assumed. **A brain dump against a live server spends credits.**
  Export `KRYTERIA_MODE=demo` for any UI poking that does not need a real model.
- Sandboxed Bash cannot reach a local port, so verify HTTP with `TestClient` in-process
  rather than `curl localhost`.
- **Schema changes do not migrate an existing database**, and `Store()` now refuses to
  open a stale one. `CREATE TABLE IF NOT EXISTS` silently leaves an existing table alone,
  so after editing `schema.sql` you must delete `data/kryteria.db` and re-seed. The guard
  compares the live columns against what `schema.sql` declares and raises a `StoreError`
  naming the missing columns and the exact two commands to fix it — a version stamp alone
  does not satisfy it, because a stamp can be written to a database that is already the
  wrong shape. **Bump `store.SCHEMA_VERSION` whenever `schema.sql` changes shape.**
  There is no Alembic yet; with no real users that is the right trade, but it needs one
  before anybody's journal depends on it.

- `PYDANTIC_AI_NO_BANNER=1` silences pydantic-ai's startup banner in test output.
- **`pydantic_ai` 2.x made `RunResult.usage` a property** that is still callable for
  back-compat — calling it emits a deprecation warning on every model call.
  `costs.usage_from_result` tests for the usage object's attributes rather than for
  callability, so the logs stay clean. Do not "simplify" that check back to `callable()`.
- **Paid runs happen now, and still need her go-ahead and an estimate first.** Twelve to
  date. Verify ordinary edits with the five suites and `TestModel` — never by exercising
  the live agents.
- **`data/prices.json` is filled in** (2026-11-11), from MGT 409 Lecture 11's "Cached
  Token Cost" table and corroborated against this workspace's HW6 data pack — two
  sources, same numbers. `gpt-6-luna`: **$0.10 input / $0.01 cached / $0.50 output** per
  1M tokens. **Known understatement:** the course also publishes a $0.125/1M cache-write
  surcharge, recorded in the file but NOT applied by `estimate_cost` (the provider does
  not report cache writes separately), so figures are slightly low on a cold cache. Say
  so in `report.html` rather than presenting the number as exact.
- **Sources must be reputable, and `backend/sources.py` enforces it.** `.gov`/`.edu`,
  academic country domains by **pattern** (`.ac.<cc>` / `.edu.<cc>`, two letters only, so
  a `.edu.com` lookalike cannot walk in), scholarly publishers, `doi.org`/PubMed, library
  catalogues. An allowlist, not a blocklist; refusals explain why. **To add a publisher,
  edit that file deliberately — never work around the gate.** Note `academia.edu` is
  explicitly refused: the `.edu` belongs to the company.
- **18 of 19 research entries are verified and citable** (17 to the criteria/evidence
  agents; `stark-coercive-control` is safety-adjacent and withheld from them). One stays
  pending: `reis-shaver-responsiveness`. Its containing volume is confirmed (Duck's
  *Handbook of Personal Relationships*, Wiley, 1988, LCCN 87022168) but nothing found
  shows the Reis & Shaver chapter is in it, or at what pages — Open Library carries no
  table of contents and `lccn.loc.gov` is unreachable from this machine. What it still
  needs is in its `citation_checked_against`.
- **When a page about a work is blocked, ask the registry instead.** ScienceDirect 403s
  automated fetching; the Ross 1977 chapter was settled from the DOI's own registered
  metadata — `curl -LH "Accept: application/x-bibtex" https://doi.org/<doi>` — which
  returns author, title, container, year and page range. Open Library's
  `openlibrary.org/books/<id>.json` and `search.json` are likewise reachable and
  authoritative for books.
- **What "verified" currently means here:** the work exists at that reference, confirmed
  against a qualifying source, and the drafted finding is a fair summary of what it is
  known for. It does **not** mean somebody read the full paper. Entries verified by
  `claude-bibliography-only` are the ones where that distinction matters most.
- **(Historical) The research knowledge base was drafted with 0 entries citable.**
  `data/research/behavioral_indicators.json` holds 19 findings across the seven areas.
  Every one is **pending**, which means invisible to the agents and unusable as a
  citation — `research_ref` must resolve to a *verified* row or the write is refused.
  Verify them by hand — **these must run from `KRYteria/`, not the workspace root**,
  which has its own unrelated `.venv`:

  ```bash
  cd "/Users/christinelittle/Yale SOM_Old/AI Foundations/KRYteria" && .venv/bin/python -m backend.verify_research list
  ```

  then `show <ref>` to see what to check, then
  `ok <ref> --url <what you opened> --by <name>`. Citations are drafted coarse
  deliberately; see the rules file for why. Do not claim anywhere that KRYteria uses
  research until some are verified.
- **The front end is React + Vite + TypeScript + Tailwind in `frontend/`.** Build it with
  the workspace Node (nvm's npm is sandbox-blocked):

  ```bash
  cd "/Users/christinelittle/Yale SOM_Old/AI Foundations/KRYteria/frontend" && PATH="../../.tools/node/bin:$PATH" npm_config_cache="../../.tools/npm-cache" npm run build
  ```

  **`frontend/dist/` is committed on purpose** so a grader needs no Node at all — see the
  note in `.gitignore`. That means **after any change under `frontend/src` you must
  rebuild and commit `dist`**, or the served app is stale.
- **Run it with `preview_start` on the `kryteria` entry** in `.claude/launch.json`, which
  pins `KRYTERIA_MODE=demo`. **This matters:** `provider.resolve_mode()` falls back to
  LIVE whenever a key is reachable, and the workspace-root `.env` always is on this
  machine — starting the server without that env var on 2026-11-09 made eleven real
  billed calls before anyone noticed. The app now logs its mode loudly at startup; read
  that line before using the UI.
- Sandboxed Bash cannot write `.claude/launch.json`; use the Terminal panel.
- **Privacy is P0 and `docs/privacy.md` is its record.** Read it before touching the
  store, the API, or anything that logs. Three things are load-bearing: every store method
  taking a row id also takes `account_id` (`_assert_owns` → `NotOwned` → **404, never
  403**); retention (`discard` / `analysis_only` / `keep_all`) runs in the same request as
  processing and overwrites text with NULL; and error strings go through
  `agents/base.redact_error` before reaching `agent_steps`. **Never add a route, field or
  feature that could signal one user about another.**
- **Do not claim the provider retains nothing.** Erasure governs this database only.
  Portkey's and the upstream provider's retention and training policies are unconfirmed —
  `docs/privacy.md` §5 lists the open questions.
- **`data/resources_us.json` is verified**, all five rows, each carrying its own
  `verified_at` shown on screen. RAINN and 911 refuse automated fetching and were
  confirmed by Christine opening them on 2026-11-16. Re-verify before each release and
  update the date when you do — a stale date is honest, a fresh date on an unchecked row
  is not.
- **No `.env` in this folder, and it must stay that way.** `app_config.py` looks here
  first, then each folder above (the workspace root holds `PORTKEY_API_KEY`), then the
  process environment — which is how a host supplies it. `.env.example` lists names only.
- The model is pinned to `gpt-6-luna` in `app_config.REQUIRED_OPENAI_MODEL`, the single
  place the name appears. `OPENAI_MODEL` is read but cannot win.
- **The repo is live and PRIVATE** at <https://github.com/celittle92/KRYteria>, and the
  app is deployed at <https://kryteria.onrender.com> with auto-deploy on push. Git writes
  and `gh` fail in sandboxed Bash; use the Terminal panel (`gh` is at
  `../.tools/gh/bin/gh`). **`zlisto` was added as a collaborator 2026-11-17** — done, not an
  open item.
- Pre-submission check, from the workspace root (offline; FAILs are the to-do list):
  `python3 check_submission.py KRYteria`
