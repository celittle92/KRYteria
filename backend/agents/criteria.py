"""Criteria Agent — clarification and behavioral indicators.

Direction A of the behavioral intelligence layer: criteria → behaviors. Off the
brain-dump path entirely, so it costs nothing on a journal entry; it serves the Criteria
screen and Checklist Mode.
"""

from __future__ import annotations

from pydantic_ai import Agent

from ..models import CriteriaOutput
from .base import AgentResult, demo_result, load_prompt, run_agent

PROMPT_PATH = "criteria.md"
AGENT_NAME = "criteria"


def build(model, store=None) -> Agent:
    """Build the agent, optionally with the research-lookup tool.

    Without a store it has no tools and can only produce ``agent_hypothesis`` indicators
    — which is the honest state when there is no knowledge base to consult.
    """
    agent = Agent(
        model,
        output_type=CriteriaOutput,
        system_prompt=load_prompt(PROMPT_PATH),
        retries=1,
    )
    if store is not None:
        register_research_tool(agent, store)
    return agent


def register_research_tool(agent: Agent, store) -> None:
    """Give an agent read access to the curated knowledge base.

    Three things this deliberately does:

      * returns **only verified** entries, so a citation the agent writes afterwards
        resolves to something a human actually checked;
      * withholds **safety-adjacent** entries, which may inform how the safety layer
        describes a behavior and must never become a checklist item;
      * carries each entry's ``caveat`` and ``do_not`` back with it, so the limits travel
        with the finding instead of being left in a file nobody reads.
    """

    @agent.tool_plain
    def lookup_research(area: str) -> list[dict]:
        """Look up curated findings for one area of the literature.

        Valid areas: attachment, emotional_regulation, interpersonal_communication,
        conflict_resolution, relationship_satisfaction_commitment,
        social_psychology_reciprocity, personality_behavior.

        Returns only entries a human has verified. An empty list means KRYteria has no
        checked finding for that area — say so, and mark anything you suggest as your own
        hypothesis rather than reaching for a citation.
        """
        notes = store.list_research_notes(area)
        return [
            {
                "ref": n["ref"],
                "concept": n["concept"],
                "finding": n["finding"],
                "citation": n["citation"],
                "caveat": n["caveat"],
                "do_not": n["do_not"],
                "indicator_hints": n["indicator_hints"],
            }
            for n in notes
        ]


def compose_input(*, value: str, desired_behavior: str, why_it_matters: str | None = None,
                  profile_name: str | None = None, tier: str | None = None,
                  want_indicators: bool = True, has_research: bool = False) -> str:
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
            "  Generate indicators for THIS profile. What a behavior looks like for a "
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
            "Suggest observable behavioral indicators — things somebody could actually "
            "notice, not traits. Mark whether each demonstrates or contradicts the "
            "criterion. Observing an indicator records an observation; it never "
            "establishes that the criterion passes.",
        ]
        if has_research:
            parts += [
                "",
                "You have a `lookup_research` tool over KRYteria's curated knowledge "
                "base. Use it when a criterion plausibly touches one of its areas.",
                "",
                "If you set source_level to established_research or research_informed, "
                "research_ref MUST be the `ref` of an entry the tool returned. Anything "
                "else is rejected — there is no way to cite something the tool did not "
                "give you, and inventing a reference is the worst thing you could do "
                "here. Carry the entry's caveat into what you say, and obey its do_not "
                "list.",
                "",
                "If the tool returns nothing for an area, say so plainly and mark your "
                "suggestions agent_hypothesis. That is honest and it needs no citation.",
            ]
        else:
            parts += [
                "",
                "You have no research tool in this run, so every indicator you suggest "
                "is agent_hypothesis. Do not cite anything. A citation you cannot "
                "retrieve is a fabrication, however confident it sounds.",
            ]
    return "\n".join(parts)


async def run(model, info, *, store=None, **kw) -> AgentResult:
    if info.mode.value == "demo":
        return demo_result(AGENT_NAME, CriteriaOutput, kw.get("entry_text", ""))
    return await run_agent(
        build(model, store), compose_input(**kw, has_research=store is not None),
        name=AGENT_NAME, info=info,
    )
