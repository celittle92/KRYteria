"""Reasoning Agent — Evidence Interrogation and Cross-Criterion Intelligence.

Interrogates the claim, never the user. Challenges positive conclusions as hard as
negative ones. Names competing priorities and hands the weighing back.
"""

from __future__ import annotations

from typing import Sequence

from pydantic_ai import Agent

from ..models import EvidenceOutput, NarrativeOutput, ReasoningOutput
from .base import AgentResult, load_prompt, run_agent
from .evidence import format_criteria, format_observations

PROMPT_PATH = "reasoning.md"
AGENT_NAME = "reasoning"

#: Language that usually hides the detail which would settle the question. Used by the
#: orchestrator to decide whether this agent is needed at all — a plain report of what
#: happened has nothing to interrogate, and asking anyway is how this becomes a deposition.
GENERALISING = (
    "always", "never", "every time", "constantly", "all the time", "doesn't care",
    "does not care", "doesn't respect", "obsessed with", "terrible at", "clearly",
    "obviously", "typical", "he's just", "she's just", "they're just", "nothing but",
    "i'm always the one", "every single",
)


def needs_interrogation(text: str, conclusions: Sequence[str] = ()) -> bool:
    haystack = " ".join([text, *conclusions]).lower()
    return any(marker in haystack for marker in GENERALISING)


def build(model) -> Agent:
    return Agent(
        model,
        output_type=ReasoningOutput,
        system_prompt=load_prompt(PROMPT_PATH),
        retries=1,
    )


def format_history(entries: Sequence[dict], decisions: Sequence[dict]) -> str:
    lines = []
    if entries:
        lines.append("Earlier entries, by id — a finding must cite these:")
        for e in entries:
            excerpt = (e.get("body") or e.get("what_happened") or "").strip()
            lines.append(f"  [{e['id']}] {e['occurred_on']}: {excerpt[:160]}")
    else:
        lines.append("There are no earlier entries. Nothing here can be a pattern yet.")
    if decisions:
        lines.append("\nDecisions the user has recorded:")
        for d in decisions[:10]:
            lines.append(f"  {d['created_at'][:10]} — {d['choice']}"
                         + (f": {d['action_text']}" if d.get("action_text") else ""))
    return "\n".join(lines)


def compose_input(*, profile_name: str, criteria: Sequence[dict],
                  narrative: NarrativeOutput, evidence: EvidenceOutput | None,
                  entries: Sequence[dict], decisions: Sequence[dict],
                  entry_text: str) -> str:
    parts = [
        format_criteria(profile_name, criteria),
        "",
        format_observations(narrative),
        "",
        "The entry in the user's own words, for quoting claims back accurately:",
        "<<<JOURNAL ENTRY>>>",
        entry_text.strip(),
        "<<<END JOURNAL ENTRY>>>",
        "",
        format_history(entries, decisions),
    ]
    if evidence and evidence.mappings:
        parts += ["", "Mappings the Evidence agent proposed:"]
        parts += [
            f"  observation [{m.observation_index}] → criterion [{m.criterion_id}]: "
            f"{m.relation}"
            for m in evidence.mappings
        ]
    parts += [
        "",
        "Interrogate the claims — at most three material questions, and challenge "
        "favourable conclusions as hard as unfavourable ones. Note where one behaviour "
        "touches several criteria. Where criteria pull against each other, name the "
        "trade-off and ask the user how they weigh it; do not settle it yourself.",
    ]
    return "\n".join(parts)


async def run(model, info, **kw) -> AgentResult:
    return await run_agent(
        build(model), compose_input(**kw), name=AGENT_NAME, info=info,
    )
