"""Reflection Agent — questions, alternatives, reconciliation, and the decision options.

Asks the question. Never answers it.
"""

from __future__ import annotations

from typing import Sequence

from pydantic_ai import Agent

from ..models import ReasoningOutput, ReflectionOutput
from .base import AgentResult, demo_result, load_prompt, run_agent

PROMPT_PATH = "reflection.md"
AGENT_NAME = "reflection"

#: Offered when the safety layer has NOT fired. `talk` and `boundary` are withheld after a
#: safety concern, because suggesting a confrontation is exactly wrong where safety may be
#: at risk; `undecided` is always available because it is a real answer.
ORDINARY_OPTIONS = ("talk", "boundary", "more_time", "gather_info", "reconsider",
                    "revise_criterion", "undecided")
POST_SAFETY_OPTIONS = ("more_time", "gather_info", "reconsider", "undecided")


def build(model) -> Agent:
    return Agent(
        model,
        output_type=ReflectionOutput,
        system_prompt=load_prompt(PROMPT_PATH),
        retries=1,
    )


def compose_input(
    *,
    entry_text: str,
    reasoning: ReasoningOutput | None = None,
    postponement_count: int = 0,
    probe_due: bool = False,
    broader_evidence: Sequence[str] = (),
    safety_fired: bool = False,
    cooldown_visits: int = 0,
    new_evidence_since_last: bool = True,
    mostly_about_the_writer: bool = False,
) -> str:
    parts = [
        "The user's entry:",
        "<<<JOURNAL ENTRY>>>",
        entry_text.strip(),
        "<<<END JOURNAL ENTRY>>>",
    ]
    if mostly_about_the_writer:
        # Reflection does not see the observations, so the one fact it needs from them is
        # handed over explicitly. Without this the agent asks about the other person's
        # compatibility on an entry whose subject was the writer's own conduct — which is
        # the failure the `about` field was added to prevent.
        parts += [
            "",
            "NOTE: most of this entry is about the WRITER'S own conduct, choices and "
            "uncertainty rather than about the person being assessed. Ask about their "
            "own agency — what they would choose, change, or need to be true — not about "
            "whether the other person can accommodate them. Hold them to account without "
            "blaming them, and do not turn the question into an accusation. Take every "
            "premise from what they wrote: do not credit them with a decision, intention "
            "or commitment the entry does not state.",
        ]
    if broader_evidence:
        parts += [
            "",
            "What the accumulated record holds. Set the entry's immediate feeling beside "
            "this. Symmetrically: do not let today erase the record, and do not let the "
            "record dismiss today.",
        ]
        parts += [f"  - {b}" for b in broader_evidence]
    if reasoning and reasoning.cross_criterion:
        parts += ["", "Trade-offs the Reasoning agent identified:"]
        parts += [f"  - {n.explanation}" for n in reasoning.cross_criterion]
    if probe_due:
        parts += [
            "",
            f"The user has chosen to give this more time {postponement_count} times on "
            "the same concern. You may ask the signature question — 'What new information "
            "are you waiting for that you don't already have?' — once, plainly, with no "
            "preamble and no recommendation after it. Set is_postponement_probe. Waiting "
            "is a legitimate decision and you never express disappointment at it.",
        ]
    if cooldown_visits >= 3 and not new_evidence_since_last:
        parts += [
            "",
            f"This ground has been covered {cooldown_visits} times with no new evidence "
            "since the last pass. You may suggest resting it — but only with all three of "
            "what is known, what is unknown, and what new information would change it, "
            "and an interval the user picks. Their distress is not evidence that they are "
            "deciding badly.",
        ]
    options = POST_SAFETY_OPTIONS if safety_fired else ORDINARY_OPTIONS
    parts += [
        "",
        "Decision options you may offer: " + ", ".join(options) + ".",
    ]
    if safety_fired:
        parts += [
            "A safety concern was identified in this entry. Do not offer having a "
            "conversation or setting a boundary as though the situation were ordinary.",
        ]
    parts += [
        "",
        "Ask one question. Offer alternatives as possibilities, never as the correct "
        "reading. Close by asking what they make of it, not by telling them what it means.",
    ]
    return "\n".join(parts)


async def run(model, info, **kw) -> AgentResult:
    if info.mode.value == "demo":
        return demo_result(AGENT_NAME, ReflectionOutput, kw.get("entry_text", ""))
    return await run_agent(
        build(model), compose_input(**kw), name=AGENT_NAME, info=info,
    )
