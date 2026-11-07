"""Criteria Agent — clarification and behavioural indicators.

Direction A of the behavioural intelligence layer: criteria → behaviours. Off the
brain-dump path entirely, so it costs nothing on a journal entry; it serves the Criteria
screen and Checklist Mode.
"""

from __future__ import annotations

from pydantic_ai import Agent

from ..models import CriteriaOutput
from .base import AgentResult, load_prompt, run_agent

PROMPT_PATH = "criteria.md"
AGENT_NAME = "criteria"


def build(model) -> Agent:
    return Agent(
        model,
        output_type=CriteriaOutput,
        system_prompt=load_prompt(PROMPT_PATH),
        retries=1,
    )


def compose_input(*, value: str, desired_behavior: str, why_it_matters: str | None = None,
                  profile_name: str | None = None, tier: str | None = None,
                  want_indicators: bool = True) -> str:
    parts = [
        "The user's criterion, in their own words:",
        f"  Value: {value}",
        f"  What meeting it looks like: {desired_behavior}",
    ]
    if why_it_matters:
        parts.append(f"  Why it matters to them: {why_it_matters}")
    if profile_name:
        parts.append(f"  Profile: {profile_name}" + (f" ({tier})" if tier else ""))
        parts.append(
            "  Generate indicators for THIS profile. What a behaviour looks like for a "
            "long-term partner and for a casual encounter are not the same things."
        )
    parts += [
        "",
        "This criterion is theirs. Do not judge, rank, or discourage it, whatever it is. "
        "You may suggest clearer wording and note genuine ambiguity, but the wording stays "
        "theirs unless they accept a change.",
    ]
    if want_indicators:
        parts += [
            "",
            "Suggest observable behavioural indicators — things somebody could actually "
            "notice, not traits. Mark whether each demonstrates or contradicts the "
            "criterion. Cite any that rest on research; say agent_hypothesis where you are "
            "extrapolating, which needs no citation. Observing an indicator records an "
            "observation; it never establishes that the criterion passes.",
        ]
    return "\n".join(parts)


async def run(model, info, **kw) -> AgentResult:
    return await run_agent(
        build(model), compose_input(**kw), name=AGENT_NAME, info=info,
    )
