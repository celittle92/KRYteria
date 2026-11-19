"""Evidence Agent — maps observations to the SELECTED profile's criteria.

The profile is the whole frame. The agent is handed one profile's criteria and sees no
others, so applying a Husband standard to a one-night-stand assessment is not something it
can be persuaded into — it does not have the rows.
"""

from __future__ import annotations

from typing import Sequence

from pydantic_ai import Agent

from ..models import EvidenceOutput, NarrativeOutput
from .base import AgentResult, demo_result, load_prompt, run_agent

PROMPT_PATH = "evidence.md"
AGENT_NAME = "evidence"


def build(model) -> Agent:
    return Agent(
        model,
        output_type=EvidenceOutput,
        system_prompt=load_prompt(PROMPT_PATH),
        retries=1,
    )


def format_criteria(profile_name: str, criteria: Sequence[dict]) -> str:
    """Only this profile's criteria, with this profile's tiers.

    Criteria the user marked not applicable are listed as such rather than omitted — the
    agent should know the criterion exists and is out of scope here, so it does not report
    it as missing information or try to gather evidence for it.
    """
    if not criteria:
        return f"The profile '{profile_name}' has no criteria configured yet."
    lines = [f"Criteria configured on the profile '{profile_name}':"]
    for c in criteria:
        if c.get("relevance") == "not_applicable":
            lines.append(
                f"  [{c['criterion_id']}] {c['value']} — NOT APPLICABLE to this profile. "
                "Do not assess it and do not report it as missing information."
            )
        else:
            # A criterion pasted in as a list may name a standard without saying what
            # meeting it looks like, and the app does not write that half for the user.
            # Send the name alone rather than a trailing dash and an empty description,
            # which reads as a field the model should fill in.
            behaviour = (c.get("desired_behavior") or "").strip()
            lines.append(
                f"  [{c['criterion_id']}] {c['value']} ({c['tier']})"
                + (f" — {behaviour}" if behaviour else "")
            )
    lines.append(
        "\nThese are the only criteria in scope. The user may hold others under different "
        "profiles; they are not yours to assess here."
    )
    return "\n".join(lines)


#: How each `about` value is announced to the agents. Spelled out rather than passed as a
#: bare enum: "me" in a list of observations is easy to skim past, and this field decides
#: whether a sentence may become evidence about somebody else.
#:
#: The "me" mark used to end "…not evidence about the other person". That absolute, sitting
#: beside every observation, beat the nuance in the prompt: a live run on 2026-11-18 filed
#: the writer's own sentence about Catherine's intelligence, career and humour as one `me`
#: reaction and mapped none of it, where the undefended run had correctly mapped four
#: supporting rows. A label should say what a thing **is**; what to do with it belongs to
#: the prompt, which can hold the exceptions. See `prompts/evidence.md`.
_ABOUT = {
    "me": "  (ABOUT THE WRITER — their own conduct or their own state)",
    "them": "  (about the person being assessed)",
    "both": "  (about both of them)",
    "unclear": "  (whose conduct this describes is unclear)",
}


def format_observations(narrative: NarrativeOutput) -> str:
    lines = ["Observations extracted from the entry, by index:"]
    for i, obs in enumerate(narrative.observations):
        mark = "" if obs.certainty == "stated" else "  (INFERRED — not something the user said)"
        lines.append(f"  [{i}] {obs.kind}: {obs.text}{mark}{_ABOUT.get(obs.about, '')}")
    mine = sum(1 for o in narrative.observations if o.about == "me")
    if mine and mine >= len(narrative.observations) / 2:
        # Said once, loudly, rather than left for the agent to notice from the marks. An
        # entry that is mostly about the writer is the case this whole rule exists for.
        lines.append(
            f"\nNOTE: {mine} of {len(narrative.observations)} observations are about the "
            "WRITER'S own conduct. This entry is largely about them, not about the person "
            "being assessed. Do not convert it into a page of open questions about "
            "somebody who barely appears in it. Equally, do not over-correct: map what "
            "the writer did report about her, and a criterion that asks how the writer "
            "feels is answered by a 'me' observation."
        )
    if narrative.user_conclusions:
        lines.append(
            "\nConclusions the user stated. These are their interpretations, not events, "
            "and they are not evidence on their own:"
        )
        lines.extend(f"  - {c}" for c in narrative.user_conclusions)
    return "\n".join(lines)


def compose_input(profile_name: str, criteria: Sequence[dict],
                  narrative: NarrativeOutput) -> str:
    return (
        format_criteria(profile_name, criteria)
        + "\n\n"
        + format_observations(narrative)
        + "\n\nMap each observation that bears on a criterion, using supporting, "
          "contradicting, complicating or unrelated. Where an observation touches a "
          "criterion without settling it, record it as insufficient and say why. "
          "Observations that relate to nothing go in unmapped_observation_indexes — do "
          "not force-fit them."
    )


async def run(model, info, *, profile_name: str, criteria: Sequence[dict],
              narrative: NarrativeOutput) -> AgentResult:
    if info.mode.value == "demo":
        return demo_result(AGENT_NAME, EvidenceOutput, "", list(criteria))
    return await run_agent(
        build(model), compose_input(profile_name, criteria, narrative),
        name=AGENT_NAME, info=info,
    )
