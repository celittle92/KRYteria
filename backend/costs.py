"""Token and cost accounting.

Two rules carried from the HW6 work and the final-project rubric:

  * **Measured, never invented.** Token counts come from what the provider reported on a
    real call. If the provider did not report cached input tokens, that is recorded as
    ``None`` — unknown — and never as zero. "The cache was cold" and "we were not told"
    are different facts and a tokenomics section that merges them is wrong in a way
    nobody reading it can see.

  * **Simulated usage is excluded.** Demo-mode steps carry ``is_simulated`` and are kept
    out of every token and cost total. A demo must never contaminate a measured figure.

Prices live in ``data/prices.json`` so the pinned model and the cost figures cannot drift
apart.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
PRICES_PATH = PROJECT_DIR / "data" / "prices.json"


@dataclass(frozen=True)
class Usage:
    """One model call's accounting. ``cached_input_tokens is None`` means unknown."""

    input_tokens: int = 0
    cached_input_tokens: int | None = None
    output_tokens: int = 0
    model_name: str | None = None
    latency_ms: int = 0
    simulated: bool = False

    @property
    def uncached_input_tokens(self) -> int:
        if self.cached_input_tokens is None:
            return self.input_tokens
        return max(0, self.input_tokens - self.cached_input_tokens)


def load_prices(model_name: str) -> dict[str, float] | None:
    if not PRICES_PATH.is_file():
        return None
    blob = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
    return blob.get("models", {}).get(model_name)


def estimate_cost(usage: Usage) -> float:
    """Dollars for one call, from published per-1M-token prices.

    Returns 0.0 for simulated usage and for a model we have no prices for — in the
    latter case the caller should say the figure is unavailable rather than print a zero
    as though it were free.
    """
    if usage.simulated or not usage.model_name:
        return 0.0
    prices = load_prices(usage.model_name)
    if not prices:
        return 0.0
    per_million = 1_000_000.0
    cached = usage.cached_input_tokens or 0
    cost = (
        usage.uncached_input_tokens * prices.get("input", 0.0) / per_million
        + cached * prices.get("cached_input", prices.get("input", 0.0)) / per_million
        + usage.output_tokens * prices.get("output", 0.0) / per_million
    )
    return round(cost, 8)


def have_prices_for(model_name: str) -> bool:
    return load_prices(model_name) is not None


def usage_from_result(result: Any, *, model_name: str | None, simulated: bool,
                      latency_ms: int = 0) -> Usage:
    """Read PydanticAI's reported usage. Never guesses a number it was not given."""
    # `usage` is a property in pydantic-ai 2.x and was a method earlier. Accept both, but
    # test for the usage object's own attributes rather than for callability — the 2.x
    # property returns an object that is *also* callable for backwards compatibility, and
    # calling it emits a deprecation warning. Getting this wrong would not break the
    # figures, but it would fill the logs with noise on every single model call.
    _USAGE_ATTRS = ("input_tokens", "request_tokens", "prompt_tokens", "details")
    try:
        reported = result.usage
        if not any(hasattr(reported, a) for a in _USAGE_ATTRS) and callable(reported):
            reported = reported()
    except Exception:
        return Usage(model_name=model_name, simulated=simulated, latency_ms=latency_ms)
    if reported is None:
        return Usage(model_name=model_name, simulated=simulated, latency_ms=latency_ms)

    def pick(*names: str) -> int | None:
        for n in names:
            v = getattr(reported, n, None)
            if isinstance(v, int):
                return v
        details = getattr(reported, "details", None) or {}
        for n in names:
            v = details.get(n)
            if isinstance(v, int):
                return v
        return None

    return Usage(
        input_tokens=pick("input_tokens", "request_tokens", "prompt_tokens") or 0,
        # Deliberately not defaulted to 0 — see the module docstring.
        cached_input_tokens=pick("cache_read_tokens", "cached_tokens",
                                 "cache_read_input_tokens"),
        output_tokens=pick("output_tokens", "response_tokens", "completion_tokens") or 0,
        model_name=model_name,
        latency_ms=latency_ms,
        simulated=simulated,
    )


def project_monthly(cost_per_run: float, runs_per_user_per_month: int,
                    users: int) -> dict[str, Any]:
    """Scale projection for the report. Assumptions are returned, not buried."""
    per_user = cost_per_run * runs_per_user_per_month
    return {
        "cost_per_run_usd": round(cost_per_run, 6),
        "runs_per_user_per_month": runs_per_user_per_month,
        "cost_per_user_per_month_usd": round(per_user, 4),
        "users": users,
        "monthly_total_usd": round(per_user * users, 2),
        "assumptions": [
            f"{runs_per_user_per_month} brain dumps per user per month",
            "cost per run measured from real runs, not estimated",
            "model inference only — excludes hosting, storage and bandwidth",
            "assumes cache behavior observed in testing holds at scale",
        ],
    }
