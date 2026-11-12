"""Reasoning Agent — Evidence Interrogation and Cross-Criterion Intelligence.

Interrogates the claim, never the user. Challenges positive conclusions as hard as
negative ones. Names competing priorities and hands the weighing back.
"""

from __future__ import annotations

from typing import Sequence

from pydantic_ai import Agent

from ..models import EvidenceOutput, NarrativeOutput, ReasoningOutput
from .base import AgentResult, demo_result, load_prompt, run_agent
from .evidence import format_criteria, format_observations

PROMPT_PATH = "reasoning.md"
AGENT_NAME = "reasoning"

#: A fallback only. See ``needs_interrogation``.
GENERALISING = (
    "always", "never", "every time", "constantly", "all the time", "doesn't care",
    "does not care", "doesn't respect", "obsessed with", "terrible at", "clearly",
    "obviously", "typical", "he's just", "she's just", "they're just", "nothing but",
    "i'm always the one", "every single",
)


def needs_interrogation(text: str, conclusions: Sequence[str] = ()) -> bool:
    """Does this entry contain something to interrogate?

    **The primary signal is structural: did the writer state a conclusion?** The
    Narrative agent already separates conclusions from events — *"he doesn't respect my
    time"* from *"he arrived 35 minutes late"* — and a stated conclusion is precisely
    what Evidence Interrogation exists to examine. If there is one, this agent runs.

    WHY IT IS NOT THE KEYWORD LIST ANY MORE. It was, until the first live A/B run on
    2026-11-11 measured the product's most load-bearing claim and found it absent. The
    cause was here: ``"He's completely unreliable. I can't count on him for anything."``
    matches none of ``GENERALISING`` — not *completely*, not *can't count on* — so this
    returned False, the orchestrator skipped Reasoning, and the three journal entries
    that contradicted the conclusion were never sent to any model at all.

    A hand-written list of generalising words gating the agent whose entire job is
    interrogating generalising claims is the blocklist mistake in its purest form: it
    catches the phrasings somebody thought of, and the one that matters is the one
    nobody listed. More words would not have fixed it. Routing on a signal the pipeline
    already produces does.

    The keyword list survives as a **fallback**, for the case where Narrative returned no
    conclusions but the raw text is sweeping anyway — a thin narrative result should not
    also cost the user their interrogation. It can only add runs, never suppress one.

    The cost is deliberate: Reasoning now runs on most entries that contain an opinion,
    which is most entries. That is one extra model call on an entry where the user drew a
    conclusion, and drawing conclusions is the thing this product exists to examine.
    """
    if any((c or "").strip() for c in conclusions):
        return True
    return any(marker in (text or "").lower() for marker in GENERALISING)


def build(model) -> Agent:
    return Agent(
        model,
        output_type=ReasoningOutput,
        system_prompt=load_prompt(PROMPT_PATH),
        retries=1,
    )


def format_history(entries: Sequence[dict], decisions: Sequence[dict],
                   current_entry_id: int | None = None) -> str:
    """The record, for citing findings against.

    The entry being analysed is **labelled, not hidden.**

    It used to be excluded outright, to stop a conclusion corroborating itself. That was
    an over-correction, and the first live run said so in its own words — the agent
    wrote, in a ``gap_note``: *"The current entry supplies a third reported instance, but
    no entry ID for it is provided, so only two distinct entries can be cited here."* It
    had found three occasions, could only cite two, and the pattern was pushed below
    ``MIN_SUPPORT`` as a result.

    Two different things were conflated. Today's entry **is** legitimate evidence of what
    happened today. What it must not be is *prior* corroboration for the conclusion drawn
    from it. Labelling it separates those: the agent can count it as an instance and
    cannot mistake it for independent support.
    """
    cur = [e for e in entries if e.get("id") == current_entry_id]
    earlier = [e for e in entries
               if current_entry_id is None or e.get("id") != current_entry_id]

    def line(e: dict) -> str:
        excerpt = (e.get("body") or e.get("what_happened") or "").strip()
        return f"  [{e['id']}] {e['occurred_on']}: {excerpt[:160]}"

    lines = []
    if cur:
        lines.append(
            "The entry you are reading now, so you can cite it as one occasion:")
        lines.extend(line(e) for e in cur)
        lines.append(
            "  NOTE: this one is today's. Count it as an instance if it is one, but it "
            "cannot corroborate a conclusion drawn from itself — only the earlier "
            "entries below can do that.")
        lines.append("")
    if earlier:
        lines.append("Earlier entries, by id — a finding must cite these:")
        lines.extend(line(e) for e in earlier)
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
                  entry_text: str, current_entry_id: int | None = None) -> str:
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
        format_history(entries, decisions, current_entry_id),
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
    if info.mode.value == "demo":
        return demo_result(AGENT_NAME, ReasoningOutput, kw.get("entry_text", ""))
    return await run_agent(
        build(model), compose_input(**kw), name=AGENT_NAME, info=info,
    )
