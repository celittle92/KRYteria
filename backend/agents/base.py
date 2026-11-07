"""Shared machinery for KRYteria's agents.

Every agent module in this package:

  * declares ``PROMPT_PATH`` and reads it **at runtime** — no prompt is ever inlined as a
    string literal in Python, and a prompt file no agent loads is a bug;
  * declares a Pydantic output type, so nothing a model returns reaches the store
    unvalidated;
  * holds only the tools its roster row allows.

``run_agent`` is the single place a model call happens, so token accounting, timing, the
execution log and error handling cannot be forgotten by an individual agent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import costs
from ..provider import ProviderInfo

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Read a runtime prompt from ``backend/prompts/``.

    Called on every run rather than cached at import, so editing a prompt does not need a
    restart and the file is demonstrably the thing being sent to the model.
    """
    path = PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Prompt file missing: {path}. Every agent loads its own prompt at runtime."
        )
    return path.read_text(encoding="utf-8")


@dataclass
class AgentResult:
    """One agent's run: its validated output, what it cost, and what went wrong."""

    agent: str
    output: Any = None
    usage: costs.Usage | None = None
    cost_usd: float = 0.0
    latency_ms: int = 0
    ok: bool = True
    error: str | None = None
    tool_calls: list[str] = field(default_factory=list)

    @property
    def simulated(self) -> bool:
        return bool(self.usage and self.usage.simulated)


async def run_agent(
    agent: Any,
    prompt: str,
    *,
    name: str,
    info: ProviderInfo,
    deps: Any = None,
) -> AgentResult:
    """Run one agent and account for it.

    A validation failure is caught and returned as ``ok=False`` rather than raised. The
    orchestrator surfaces it as a recoverable state: a model that produced malformed or
    over-confident output must not take the request down, and must not be written to the
    database either.
    """
    started = time.perf_counter()
    try:
        result = await agent.run(prompt, deps=deps)
    except Exception as exc:  # validation failure, provider error, timeout
        elapsed = int((time.perf_counter() - started) * 1000)
        return AgentResult(
            agent=name, ok=False, error=f"{type(exc).__name__}: {exc}",
            latency_ms=elapsed,
            usage=costs.Usage(model_name=info.model_name, simulated=info.simulated),
        )

    elapsed = int((time.perf_counter() - started) * 1000)
    usage = costs.usage_from_result(
        result, model_name=info.model_name, simulated=info.simulated,
        latency_ms=elapsed,
    )
    return AgentResult(
        agent=name,
        output=getattr(result, "output", getattr(result, "data", None)),
        usage=usage,
        cost_usd=costs.estimate_cost(usage),
        latency_ms=elapsed,
        tool_calls=_tool_names(result),
    )


def _tool_names(result: Any) -> list[str]:
    """Tool NAMES only.

    Deliberately never argument values: the execution log is shown on screen and pasted
    into a report, and it is exactly where a user's private writing would leak while
    looking like harmless telemetry.
    """
    names: list[str] = []
    try:
        for message in result.all_messages():
            for part in getattr(message, "parts", []):
                tool_name = getattr(part, "tool_name", None)
                if tool_name:
                    names.append(str(tool_name))
    except Exception:
        return names
    return names
