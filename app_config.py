"""Portkey settings for KRYteria. The one place the model name and credentials are read.

Where the key comes from, in order:

  1. ``.env`` in this repo's own folder
  2. ``.env`` in the folder above it  — this is where the teaching staff keep theirs
  3. the process environment           — this is how a host supplies it

The MGT 409 final-project requirements are explicit that every submission is cloned into
one ``submissions/`` folder with a single shared ``.env`` sitting one level *above* each
repo. ``load_dotenv`` never overrides a value that is already set, so walking from here
outward means the nearest ``.env`` wins and a host's real environment variable beats both.

Everything else in the app imports ``load_settings()`` rather than touching the
environment, because the two can disagree before ``load_dotenv`` has run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

#: The only model this project may ever bill.
#:
#: The course Portkey key permits ``gpt-6-luna`` and nothing else — using another model on
#: it is both a billing failure and a lost mark. ``OPENAI_MODEL`` is still read, but a
#: value naming anything else is **ignored** rather than honoured, and the ignored value is
#: reported on ``Settings.model_override_ignored`` so the substitution is visible instead
#: of silent.
#:
#: This matters more here than in a single-script homework: the semester default in
#: ``AGENT.MD`` is ``gpt-5.6-luna``, and KRYteria runs five agents. One stray
#: ``OPENAI_MODEL`` in a shared ``.env`` would otherwise re-bill the whole workflow at once,
#: on every request, for every user of a hosted app.
#:
#: ``data/prices.json`` prices this same model, so the cost figures the app reports and the
#: model actually billed cannot drift apart.
REQUIRED_OPENAI_MODEL = "gpt-6-luna"

#: Accepted key names. The staff ``.env`` carries exactly these two and the requirements
#: say an app must use one of them, spelled this way.
PORTKEY_KEY_NAME = "PORTKEY_API_KEY"
OPENAI_KEY_NAME = "OPENAI_API_KEY"


#: Which gateway the model is reached through.
#:
#: Portkey is the course route and stays the default. The direct-OpenAI route exists
#: because on 2026-11-23 the shared course Portkey key began returning
#: ``401 Invalid API Key. Error Code: 03`` — for every key tried, on the host and on a
#: laptop alike — and the teaching staff handed out an ``OPENAI_API_KEY`` instead. The
#: requirements already say their ``.env`` carries **both** names, so an app that can
#: only read one of them fails the moment the other is the working one.
#:
#: ``KRYTERIA_PROVIDER`` forces a route: ``portkey`` | ``openai`` | ``auto`` (default).
#: Under ``auto`` the first key present wins, Portkey first.
PROVIDER_ENV_NAME = "KRYTERIA_PROVIDER"
PROVIDER_PORTKEY = "portkey"
PROVIDER_OPENAI = "openai"


@dataclass(frozen=True)
class Settings:
    """Resolved configuration. Never log or render ``portkey_api_key``."""

    portkey_api_key: str
    model_name: str
    portkey_base_url: str
    portkey_provider: str | None
    portkey_config_id: str | None
    model_override_ignored: str | None = None
    env_source: str = "process environment"
    #: ``portkey`` or ``openai`` — which gateway ``build_model`` will actually call.
    provider_route: str = PROVIDER_PORTKEY

    @property
    def key_fingerprint(self) -> str:
        """A safe thing to show in a health check: proves a key loaded, reveals nothing."""
        return f"…{self.portkey_api_key[-4:]}" if len(self.portkey_api_key) >= 4 else "set"

    @property
    def key_name_in_use(self) -> str:
        """Which of the two accepted names supplied the key that will be used."""
        return PORTKEY_KEY_NAME if self.provider_route == PROVIDER_PORTKEY else OPENAI_KEY_NAME


def _load_dotenv_files() -> str | None:
    """Load this folder's .env, then each ancestor's. Nearest wins.

    Returns the path of the nearest ``.env`` that actually exists, for the health check to
    report — so "the app cannot find your key" is a diagnosable statement rather than a
    guess. Returns ``None`` when the environment is supplying the key directly.
    """
    found: str | None = None
    for directory in (PROJECT_DIR, *PROJECT_DIR.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            if found is None:
                found = str(candidate)
    return found


def env_file_in_use() -> str | None:
    """Which ``.env`` the app reads, whether or not it holds a usable key.

    **The failure path needs this more than the success path does.** `load_settings`
    works out the same answer and then raises before returning it when the key is
    missing, so `/api/health` reported `env_source: null` in precisely the situation the
    field exists for — somebody whose key is not being picked up, trying to find out
    which file the app is actually reading.

    Found on 2026-11-21 by `tools/fresh_clone_check.sh`, which writes an empty
    `PORTKEY_API_KEY` one level above the clone and asserts the app finds that file. It
    had been passing for the wrong reason: a stale `export` in the shell was supplying a
    real key, so `load_settings` returned normally. With the export gone the check went
    red and the reporting gap it had been masking showed up — which is the staff's own
    scenario, since their `.env` sits one level above the repo.

    Safe to call repeatedly: `load_dotenv` does not overwrite a variable that is already
    set.
    """
    return _load_dotenv_files()


def _choose_route() -> tuple[str, str]:
    """Pick the gateway and the key, or explain precisely what is missing.

    Portkey first, because it is the course route. ``KRYTERIA_PROVIDER`` overrides, and
    a forced route that has no key is an error rather than a silent fall-through — being
    quietly billed through a gateway you did not choose is worse than stopping.
    """
    forced = (os.getenv(PROVIDER_ENV_NAME) or "auto").strip().lower()
    portkey_key = os.getenv(PORTKEY_KEY_NAME)
    openai_key = os.getenv(OPENAI_KEY_NAME)

    if forced == PROVIDER_PORTKEY:
        if not portkey_key:
            raise RuntimeError(
                f"{PROVIDER_ENV_NAME}={PROVIDER_PORTKEY} but {PORTKEY_KEY_NAME} is not set."
            )
        return PROVIDER_PORTKEY, portkey_key
    if forced == PROVIDER_OPENAI:
        if not openai_key:
            raise RuntimeError(
                f"{PROVIDER_ENV_NAME}={PROVIDER_OPENAI} but {OPENAI_KEY_NAME} is not set."
            )
        return PROVIDER_OPENAI, openai_key
    if forced not in ("auto", ""):
        raise RuntimeError(
            f"{PROVIDER_ENV_NAME}={forced!r} is not one of "
            f"{PROVIDER_PORTKEY}, {PROVIDER_OPENAI}, auto."
        )

    if portkey_key:
        return PROVIDER_PORTKEY, portkey_key
    if openai_key:
        return PROVIDER_OPENAI, openai_key
    raise RuntimeError(
        f"Neither {PORTKEY_KEY_NAME} nor {OPENAI_KEY_NAME} is set.\n"
        f"KRYteria looks for a .env file in {PROJECT_DIR}, then in each folder above "
        f"it, then in the process environment.\n"
        f"Copy .env.example to .env and fill in one of them. If a key is present but "
        f"rejected, set {PROVIDER_ENV_NAME}={PROVIDER_OPENAI} to use {OPENAI_KEY_NAME} "
        f"instead."
    )


def load_settings(model_override: str | None = None) -> Settings:
    env_source = _load_dotenv_files()
    route, api_key = _choose_route()

    requested = (model_override or os.getenv("OPENAI_MODEL") or "").strip()
    ignored = requested if requested and requested != REQUIRED_OPENAI_MODEL else None

    return Settings(
        portkey_api_key=api_key,
        model_name=REQUIRED_OPENAI_MODEL,
        portkey_base_url=os.getenv("PORTKEY_BASE_URL", DEFAULT_PORTKEY_BASE_URL),
        portkey_provider=os.getenv("PORTKEY_PROVIDER"),
        portkey_config_id=os.getenv("PORTKEY_CONFIG_ID"),
        model_override_ignored=ignored,
        env_source=env_source or "process environment",
        provider_route=route,
    )


def build_portkey_client(settings: Settings) -> AsyncOpenAI:
    """The OpenAI-compatible client for whichever route ``load_settings`` chose.

    Named for Portkey because that is still the default and every caller already says
    so. On the direct route it is a plain OpenAI client: **no Portkey headers and no
    base-URL override**, because sending ``x-portkey-api-key`` to OpenAI would leak a
    key to a service that has no business holding it.
    """
    if settings.provider_route == PROVIDER_OPENAI:
        return AsyncOpenAI(api_key=settings.portkey_api_key)

    headers = {"x-portkey-api-key": settings.portkey_api_key}
    if settings.portkey_provider:
        headers["x-portkey-provider"] = settings.portkey_provider
    if settings.portkey_config_id:
        headers["x-portkey-config"] = settings.portkey_config_id

    return AsyncOpenAI(
        api_key=settings.portkey_api_key,
        base_url=settings.portkey_base_url,
        default_headers=headers,
    )


def build_model(settings: Settings | None = None):
    """The PydanticAI model every agent in this app shares.

    ``OpenAIResponsesModel``, not the default chat-completions class: luna models reject
    function tools on ``/v1/chat/completions``, and every agent here has tools.
    """
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    settings = settings or load_settings()
    client = build_portkey_client(settings)
    return OpenAIResponsesModel(
        settings.model_name,
        provider=OpenAIProvider(openai_client=client),
    )
