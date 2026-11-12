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

- **Four test suites, all free, no API calls, no network:**

  | Suite | Interpreter | Covers |
  |---|---|---|
  | `tests/test_offline.py` | system `python3` | the store layer; stubs `backend.security` so it runs with nothing installed |
  | `tests/test_contracts.py` | `.venv/bin/python` | the Pydantic output contracts and the demo provider |
  | `tests/test_wiring.py` | `.venv/bin/python` | real Argon2id, provider resolution, agent construction on `TestModel`, budget enforcement |
  | `tests/test_api.py` | `.venv/bin/python` | the HTTP layer in demo mode, including **data isolation between accounts** and retention |

  566 checks in total as of 2026-11-09. Run all four after any change to `backend/`.

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
- **No live model call has ever been made from this project.** Verify edits with the three
  suites and with `TestModel`; a paid run needs Christine's go-ahead and an estimate first.
- **`data/prices.json` has no prices yet.** `models` is empty and the figures sit under
  `pending`. Until they are filled in from the course's published pricing,
  `estimate_cost` returns 0.0 and the app must report cost as *unavailable* rather than
  printing a zero as though a run were free.
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
- **`data/resources_us.json` is unverified.** The hotline numbers and URLs were entered
  from the charter text on 2026-11-07 and have not been checked against each
  organisation's own site. Do that before the demo and before submission.
- **No `.env` in this folder, and it must stay that way.** `app_config.py` looks here
  first, then each folder above (the workspace root holds `PORTKEY_API_KEY`), then the
  process environment — which is how a host supplies it. `.env.example` lists names only.
- The model is pinned to `gpt-6-luna` in `app_config.REQUIRED_OPENAI_MODEL`, the single
  place the name appears. `OPENAI_MODEL` is read but cannot win.
- **Nothing is committed and there is no GitHub repo yet.** Git writes and `gh` fail in
  sandboxed Bash; use the Terminal panel (`gh` is at `../.tools/gh/bin/gh`).
- Pre-submission check, from the workspace root (offline; FAILs are the to-do list):
  `python3 check_submission.py KRYteria`
