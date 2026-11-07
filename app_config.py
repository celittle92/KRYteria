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

    @property
    def key_fingerprint(self) -> str:
        """A safe thing to show in a health check: proves a key loaded, reveals nothing."""
        return f"…{self.portkey_api_key[-4:]}" if len(self.portkey_api_key) >= 4 else "set"


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


def load_settings(model_override: str | None = None) -> Settings:
    env_source = _load_dotenv_files()
    api_key = os.getenv(PORTKEY_KEY_NAME)
    if not api_key:
        raise RuntimeError(
            f"{PORTKEY_KEY_NAME} is missing.\n"
            f"KRYteria looks for a .env file in {PROJECT_DIR}, then in each folder above "
            f"it, then in the process environment.\n"
            f"Copy .env.example to .env and fill in your key, or set {PORTKEY_KEY_NAME} "
            f"in the environment."
        )

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
    )


def build_portkey_client(settings: Settings) -> AsyncOpenAI:
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
