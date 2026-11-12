"""The head-to-head: KRYteria against how this is done today.

A general-purpose chatbot is the status quo. Most people working through "was that a
problem or was it me?" open one and describe what happened. So the comparison is against
*that*, running on the same model, over the same entries, graded on the same dimensions.

TWO RULES KEEP THIS HONEST, AND BOTH COST US SOMETHING.

**The baseline gets a good prompt.** ``backend/prompts/baseline_chatbot.md`` asks for
warmth, honesty over reassurance, and acknowledged uncertainty. A rigged baseline would
produce a better-looking table and a worthless finding.

**Both systems are graded on prose only.** Every dimension here is answerable from words
a person would read. Grading KRYteria on structured output it emits and the baseline on
prose it cannot structure would measure the format, not the thinking. The structural
asymmetry is reported separately, as *capability* — what only one system produced at all
— and never folded into the score.

What this cannot do is read minds about quality. "Was the question a good one?" stays a
human judgement, and the report prints both replies side by side so a person can make it.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from .. import provider
from ..agents.base import AgentResult, load_prompt, run_agent
from ..agents.orchestrator import Orchestrator
from ..store import Store
from . import checks as checks_mod
from .scenario import build_world, new_entry, seed_resources
from .transcript import Transcript, from_brain_dump, from_prose

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
SCENARIOS = PROJECT_DIR / "tests" / "evals" / "ab_scenarios.json"

PROMPT_PATH = "baseline_chatbot.md"
BASELINE_NAME = "generic_chatbot"


def build_baseline(model) -> Agent:
    """A plain assistant: one call, no tools, no criteria, no memory of prior entries."""
    return Agent(model, output_type=str, system_prompt=load_prompt(PROMPT_PATH), retries=1)


async def run_baseline(model, info, entry_text: str) -> AgentResult:
    """How the task is done today. Deliberately given nothing KRYteria has."""
    if info.mode.value == "demo":
        return AgentResult(
            agent=BASELINE_NAME,
            output=("[demo mode] A generic assistant would reply here in prose. "
                    "Demo mode makes no model call, so this is not a comparison."),
            usage=None, cost_usd=0.0,
        )
    return await run_agent(build_baseline(model), entry_text.strip(),
                           name=BASELINE_NAME, info=info)


def load_scenarios() -> dict:
    if not SCENARIOS.is_file():
        raise FileNotFoundError(f"Missing A/B scenarios: {SCENARIOS}")
    blob = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    for s in blob.get("scenarios", []):
        if not s.get("dimensions"):
            raise ValueError(f"A/B scenario {s.get('id')!r} defines no dimensions.")
        for d in s["dimensions"]:
            if d.get("check") not in checks_mod._REGISTRY:
                raise ValueError(
                    f"A/B scenario {s['id']}: unknown check {d.get('check')!r}."
                )
            if d["check"] not in ("prose_lacks", "prose_has_one_of",
                                  "asks_a_question", "manual"):
                raise ValueError(
                    f"A/B scenario {s['id']}: {d['check']!r} reads structured output, "
                    "which the baseline cannot produce. A/B dimensions must be "
                    "answerable from prose by both systems, or the comparison measures "
                    "the output format instead of the reasoning."
                )
    return blob


def _capability(t: Transcript) -> dict:
    """What a system produced *at all* — reported beside the score, never inside it."""
    return {
        "structured_output": t.structured,
        "observations": len(t.observations),
        "observations_marked_interpretation": sum(
            1 for o in t.observations if o["kind"] == "interpretation"),
        "evidence_mappings": len(t.mappings),
        "contradicting_or_complicating": sum(
            1 for m in t.mappings if m["relation"] in ("contradicting", "complicating")),
        "insufficiency_notes": len(t.insufficient),
        "questions_raised": len(t.interrogations),
        "assessment_proposals_withheld_for_user": len(t.proposals),
        "traceable_to_entry_ids": bool(t.patterns) and all(
            p["supporting_entry_ids"] or p["contradicting_entry_ids"] for p in t.patterns),
    }


async def _run_scenario(store: Store, model, info, scenario: dict) -> dict:
    row: dict[str, Any] = {
        "id": scenario["id"],
        "title": scenario.get("title", ""),
        "why_this_one": scenario.get("why_this_one", ""),
        "user_input": scenario["user_input"],
        # Carried into the result so the report can label each column with the question
        # it was actually asking, rather than a check name.
        "dimensions": scenario["dimensions"],
        "systems": {},
    }

    # --- B: KRYteria ---------------------------------------------------------
    world = build_world(store, scenario, handle_prefix="ab")
    entry_id = new_entry(store, world, scenario["user_input"])
    orch = Orchestrator(store, model, info)
    dump = await orch.brain_dump(
        world.account_id, entry_id=entry_id, entry_text=scenario["user_input"],
        profile_id=world.profile_id, profile_name=world.profile_name,
        person_id=world.person_id, want_reflection=True,
    )
    kry = from_brain_dump(dump, world.names,
                          safety_events=[dict(e) for e in
                                         store.list_safety_events(world.account_id)])

    # --- A: the status quo ---------------------------------------------------
    base_step = await run_baseline(model, info, scenario["user_input"])
    usage = base_step.usage
    base = from_prose(
        BASELINE_NAME, str(base_step.output or ""),
        model_calls=1,
        input_tokens=usage.input_tokens if usage and not usage.simulated else 0,
        output_tokens=usage.output_tokens if usage and not usage.simulated else 0,
        latency_ms=base_step.latency_ms,
        simulated=not (usage and not usage.simulated),
        errors=[base_step.error] if base_step.error else [],
    )

    for label, t in (("kryteria", kry), (BASELINE_NAME, base)):
        rows = [checks_mod.run_check(t, d) for d in scenario["dimensions"]]
        row["systems"][label] = {
            "rows": rows,
            "passed": sum(1 for r in rows if r["outcome"] == checks_mod.PASS),
            "failed": sum(1 for r in rows if r["outcome"] == checks_mod.FAIL),
            "needs_review": sum(1 for r in rows if r["outcome"] == checks_mod.REVIEW),
            "capability": _capability(t),
            "prose": t.prose,
            "model_calls": t.model_calls,
            "input_tokens": t.input_tokens,
            "output_tokens": t.output_tokens,
            "latency_ms": t.latency_ms,
        }
    return row


async def run_ab(*, mode: str, only: list[str] | None = None,
                 db_path: Path | None = None) -> dict:
    blob = load_scenarios()
    scenarios = blob["scenarios"]
    if only:
        scenarios = [s for s in scenarios if s["id"] in set(only)]

    model, info = provider.build(mode)
    db = db_path or Path(tempfile.mkdtemp()) / f"ab_{time.time()}.db"
    store = Store(db)
    seed_resources(store)

    started = time.time()
    rows = [await _run_scenario(store, model, info, s) for s in scenarios]

    return {
        "mode": info.mode.value,
        "model": info.model_name,
        "simulated": info.simulated,
        "evidence_value": "none" if info.simulated else "real",
        "baseline_prompt": PROMPT_PATH,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "duration_s": round(time.time() - started, 2),
        "dimensions_note": (
            "Both systems are graded on prose only. Structural output is reported as "
            "capability, never scored, so the comparison measures reasoning rather than "
            "output format."),
        "scenarios": rows,
    }


def run_ab_sync(**kw) -> dict:
    return asyncio.run(run_ab(**kw))
