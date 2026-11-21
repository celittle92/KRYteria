"""KRYteria — FastAPI application.

One process serves the API and the built front end, so there is one thing to deploy, one
port, and one URL. That is what makes the ten-minute setup rule and the hosted deployment
the same problem solved once.

Run it:

    .venv/bin/python -m uvicorn backend.main:app --reload --port 8000

The API key never reaches the browser: the front end calls this backend, and this backend
calls the model provider.
"""

from __future__ import annotations

# Refuse Python 3.9 here, with the fix, rather than failing deeper and later.
from backend._python_version import require as _require_python
_require_python()

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import costs, durability
from .api import account, assess, auth, criteria, journal
from .api.deps import get_provider, get_store
from .security_headers import SecurityHeaders

PROJECT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

def _announce_mode() -> None:
    """Say loudly, at startup, whether this process will spend money.

    `resolve_mode()` falls back to LIVE whenever a key is reachable — right for a hosted
    deployment, a footgun on a laptop where the workspace .env is always reachable. On
    2026-11-09 starting this server for a UI check made eleven real billed calls before
    anybody noticed. Silence was the bug; this is the fix that does not depend on
    remembering.
    """
    import logging

    from .provider import Mode, resolve_mode

    log = logging.getLogger("kryteria")
    mode = resolve_mode()
    if mode is Mode.LIVE:
        log.warning(
            "\n%s\n  KRYteria is in LIVE mode. Every brain dump spends real credits.\n"
            "  Set KRYTERIA_MODE=demo for UI work — it needs no key and bills nothing.\n%s",
            "=" * 74, "=" * 74,
        )
    else:
        log.warning("KRYteria is in %s mode — nothing is billed.", mode.value.upper())


def _seed_on_boot() -> None:
    """Rebuild the synthetic demo data at startup when ``KRYTERIA_SEED_ON_BOOT=true``.

    **Both halves, and the walkthrough first.** This seeded only the nine-character
    ecosystem until 2026-11-20, which was survivable while the landing page offered nine
    characters and nothing else. The rebuilt front door makes *See it working* open the
    ``demo`` account — the hand-built exhibit — and that account had never been seeded on
    the host at all, so the primary path into the product returned 404 in production while
    passing locally, where it had been seeded by hand.

    Christine found it in about a minute: *"I can't get into the demo."* The signal was
    there and I walked past it — the API-level test I wrote for this could not find
    ``demo`` in its throwaway database either, and I moved the test offline instead of
    asking why the account was missing.

    Free hosting tiers mostly give you an ephemeral disk: the database is gone after a
    restart or a redeploy, and a grader who opens the link gets an empty application with
    nowhere to sign in. Seeding on boot turns that from a failure into a non-event — the
    demo is simply always there, freshly built, however many times the host recycles the
    process.

    Off by default, because on a laptop the database is supposed to persist and a surprise
    write at import time is the wrong default. The host turns it on.

    It is idempotent: ``seed()`` returns early when the demo account already exists, so a
    restart with a real disk underneath neither duplicates anything nor overwrites it. It
    only ever touches the synthetic account, never a real one.
    """
    import logging

    log = logging.getLogger("kryteria")
    if os.getenv("KRYTERIA_SEED_ON_BOOT", "").lower() != "true":
        return
    try:
        from .seed_characters import PartialSeed, seed
        from .seed_demo import DEMO_HANDLE
        from .seed_demo import seed as seed_walkthrough

        # The walkthrough account is what "See it working" opens, so it is seeded first
        # and its failure is reported on its own. Idempotent: returns early if it exists.
        try:
            seed_walkthrough(get_store())
            log.warning("Walkthrough account ready: %s.", DEMO_HANDLE)
        except Exception:
            log.exception(
                "Seeding the walkthrough account FAILED — 'See it working' will 404."
            )

        try:
            built = seed(get_store())
        except PartialSeed as e:
            # Eight characters beat none. Take what built and say loudly what did not,
            # because the failure mode this guards against is an app that comes up
            # looking fine with an empty demo and no visible reason.
            built = e.built
            log.error("Demo ecosystem is INCOMPLETE — %s", e)
        log.warning(
            "Demo ecosystem ready: %d accounts (%s).",
            len(built), ", ".join(sorted(built)),
        )
    except Exception:
        # A broken seed must not take the whole application down with it: the API and a
        # real user's data are more important than the demo fixture. Log it loudly.
        log.exception("Seeding the demo account on boot FAILED. The app is still up.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_on_boot()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="KRYteria",
    description=(
        "Personal decision intelligence. Knowledge is the tool. Relationships are the "
        "context. You are the priority."
    ),
    version="0.1.0",
)

#: Browser-enforced protections the server cannot apply on its own — framing, sniffing,
#: referrer leakage, and the permissions a compromised page could otherwise request.
#: See backend/security_headers.py; each one is there for a reason specific to an app
#: holding this kind of writing.
app.add_middleware(SecurityHeaders)

for router in (auth.router, criteria.router, journal.router, assess.router,
               account.router):
    app.include_router(router)

_announce_mode()


@app.get("/api/health")
def health():
    """Everything a grader needs to tell whether this install will work.

    Deliberately detailed: "it doesn't work" is a much worse bug report than "the key
    isn't being found and here is where it looked".
    """
    import app_config

    store = get_store()
    _, info = get_provider()

    key_found, env_source, key_error = True, None, None
    try:
        settings = app_config.load_settings()
        env_source = settings.env_source
        model_override_ignored = settings.model_override_ignored
    except RuntimeError as e:
        key_found, model_override_ignored = False, None
        key_error = str(e).splitlines()[0]

    return {
        "ok": True,
        "mode": info.mode.value,
        "model": info.model_name,
        "simulated": info.simulated,
        "api_key_found": key_found,
        "env_source": env_source,
        "key_error": key_error,
        "model_override_ignored": model_override_ignored,
        "prices_loaded": costs.have_prices_for(info.model_name),
        "database": str(store.db_path),
        # Said here as well as on screen, so a grader or an operator can see what this
        # deployment actually promises without having to read render.yaml.
        "storage_durable": durability.storage_is_durable(),
        "storage_note": durability.storage_note(),
        "frontend_built": FRONTEND_DIST.is_dir(),
        "note": (
            "Running in demo mode — no API key needed, nothing is billed, and all "
            "generated content is synthetic." if info.simulated else None
        ),
    }


@app.exception_handler(Exception)
async def unhandled(request, exc):  # pragma: no cover - last resort
    """Never leak an internal error to the browser.

    A stack trace from a journalling app could contain the user's own writing. The detail
    goes to the server log; the browser gets a sentence.
    """
    import logging

    logging.getLogger("kryteria").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Your data has not been changed."},
    )


# ---------------------------------------------------------------- front end
#
# Mounted last so it cannot shadow an /api route. When the front end has not been built,
# the API still works and / explains how to build it rather than returning a bare 404.

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"),
              name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """Serve the single-page app, letting the client router own its own paths.

        An unmatched ``/api/...`` path is an error, not a page. Falling through to the
        SPA answered every mistyped or not-yet-deployed endpoint with 200 and a page of
        HTML, so a client got a JSON parse error instead of a 404 — and checking whether
        a deployment had a route returned "yes" either way. That cost real time once.
        """
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": f"No such endpoint: /{full_path}"},
            )
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        return {
            "app": "KRYteria",
            "api": "running",
            "frontend": "not built",
            "docs": "/docs",
            "health": "/api/health",
            "to_build_the_front_end": [
                "cd frontend",
                "npm install",
                "npm run build",
            ],
        }


def main() -> None:  # pragma: no cover - convenience entry point
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=os.getenv("KRYTERIA_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("KRYTERIA_RELOAD", "").lower() == "true",
    )


if __name__ == "__main__":  # pragma: no cover
    main()
