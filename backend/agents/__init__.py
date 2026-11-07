"""KRYteria's agents.

Seven modules. Six are model-backed agents; the orchestrator routes between them and
spends no model call of its own deciding how to route.

Each agent declares ``PROMPT_PATH`` and loads that file from ``backend/prompts/`` at
runtime. None inlines a prompt as a string literal.
"""

from . import criteria, evidence, narrative, orchestrator, reasoning, reflection, safety

__all__ = [
    "orchestrator", "narrative", "safety", "evidence", "reasoning", "reflection",
    "criteria",
]
