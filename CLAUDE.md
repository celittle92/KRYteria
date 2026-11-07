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

- **Three test suites, all free, no API calls, no network:**

  | Suite | Interpreter | Covers |
  |---|---|---|
  | `tests/test_offline.py` | system `python3` | the store layer; stubs `backend.security` so it runs with nothing installed |
  | `tests/test_contracts.py` | `.venv/bin/python` | the Pydantic output contracts and the demo provider |
  | `tests/test_wiring.py` | `.venv/bin/python` | real Argon2id, provider resolution, agent construction on `TestModel`, budget enforcement |

  371 checks in total as of 2026-11-07. Run all three after any change to `backend/`.

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
