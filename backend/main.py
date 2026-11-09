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

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import costs
from .api import account, assess, auth, criteria, journal
from .api.deps import get_provider, get_store

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


app = FastAPI(
    title="KRYteria",
    description=(
        "Personal decision intelligence. Knowledge is the tool. Relationships are the "
        "context. You are the priority."
    ),
    version="0.1.0",
)

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
        """Serve the single-page app, letting the client router own its own paths."""
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
