"""Orchestrator — routing, budget enforcement, and the execution log.

Three things live here because they must not be left to a prompt:

  **Routing.** Not every brain dump needs every agent. Narrative and Safety always run,
  concurrently, on the raw text. Evidence follows. Reasoning only when there is something
  to interrogate; Reflection only when it is wanted. Three model calls for an ordinary
  entry, five at most.

  **Budget.** Per-account and global daily token caps, checked before a run starts and
  enforced in code. A hosted app spends real money when strangers use it, and a prompt
  asking a model to be frugal is not a control.

  **The safety halt.** When the Safety layer returns ``halt_and_route`` the workflow stops
  there — no mapping, no interrogation, no reflective question on top of a disclosure of
  harm. The ordinary analysis does not resume afterwards unless the user asks.

Nothing here writes an assessment status. The agents prepare; the user decides.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

from ..models import NarrativeOutput, ReasoningOutput, SafetyOutput
from ..provider import ProviderInfo
from . import criteria as criteria_agent
from . import evidence as evidence_agent
from . import narrative as narrative_agent
from . import reasoning as reasoning_agent
from . import reflection as reflection_agent
from . import safety as safety_agent
from .base import AgentResult, load_prompt

PROMPT_PATH = "orchestrator.md"

DEFAULT_DAILY_TOKENS_PER_ACCOUNT = 120_000
DEFAULT_DAILY_TOKENS_GLOBAL = 2_000_000
#: Hard ceiling on model calls in one request. No loops, no "one more pass".
MAX_AGENT_CALLS = 5


def routing_policy() -> str:
    """The orchestrator's own runtime prompt.

    Read at runtime like every other agent's, and kept as the human-readable statement of
    the routing rules the code below implements. The routing itself is deterministic —
    spending a model call to decide whether to spend model calls would be absurd.
    """
    return load_prompt(PROMPT_PATH)


@dataclass
class BrainDumpResult:
    """Everything one brain dump produced, including what it cost and what failed."""

    run_id: int | None = None
    narrative: NarrativeOutput | None = None
    safety: SafetyOutput | None = None
    evidence: Any = None
    reasoning: ReasoningOutput | None = None
    reflection: Any = None
    resources: list[dict] = field(default_factory=list)
    steps: list[AgentResult] = field(default_factory=list)
    halted: bool = False
    halt_reason: str | None = None
    status: str = "ok"
    errors: list[str] = field(default_factory=list)

    @property
    def model_calls(self) -> int:
        return len(self.steps)

    @property
    def cost_usd(self) -> float:
        return round(sum(s.cost_usd for s in self.steps if not s.simulated), 8)

    @property
    def input_tokens(self) -> int:
        return sum(s.usage.input_tokens for s in self.steps
                   if s.usage and not s.usage.simulated)

    @property
    def output_tokens(self) -> int:
        return sum(s.usage.output_tokens for s in self.steps
                   if s.usage and not s.usage.simulated)


class BudgetExceeded(RuntimeError):
    pass


class Orchestrator:
    def __init__(self, store, model, info: ProviderInfo) -> None:
        self.store = store
        self.model = model
        self.info = info
        self.per_account_cap = int(
            os.getenv("KRYTERIA_DAILY_TOKENS_PER_ACCOUNT",
                      DEFAULT_DAILY_TOKENS_PER_ACCOUNT)
        )
        self.global_cap = int(
            os.getenv("KRYTERIA_DAILY_TOKENS_GLOBAL", DEFAULT_DAILY_TOKENS_GLOBAL)
        )

    # ------------------------------------------------------------- budget

    def check_budget(self, account_id: int) -> None:
        """Checked before a run starts, in code.

        Simulated usage never reaches ``usage_daily``, so demo mode cannot exhaust a
        budget and cannot be used to mask one either.
        """
        if self.info.simulated:
            return
        today = self.store.usage_today(account_id)
        used = today["input_tokens"] + today["output_tokens"]
        if used >= self.per_account_cap:
            raise BudgetExceeded(
                f"Daily token budget reached for this account ({used:,} of "
                f"{self.per_account_cap:,}). It resets at midnight UTC."
            )
        glob = self.store.usage_all_accounts_today()
        used_global = glob["input_tokens"] + glob["output_tokens"]
        if used_global >= self.global_cap:
            raise BudgetExceeded(
                f"KRYteria's daily token budget is exhausted ({used_global:,} of "
                f"{self.global_cap:,}). It resets at midnight UTC."
            )

    # ------------------------------------------------------------- logging

    def _record(self, run_id: int, seq: int, step: AgentResult) -> None:
        usage = step.usage
        self.store.log_step(
            run_id, seq, step.agent,
            tool_calls=step.tool_calls,           # names only; never argument values
            model_name=self.info.model_name,
            input_tokens=usage.input_tokens if usage else 0,
            cached_input_tokens=usage.cached_input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else 0,
            estimated_cost_usd=step.cost_usd,
            latency_ms=step.latency_ms,
            ok=step.ok,
            is_simulated=self.info.simulated,
            error_message=step.error,
        )
        if usage and not usage.simulated:
            self.store.add_usage(
                self.store_account, input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens, cost_usd=step.cost_usd,
            )

    # ------------------------------------------------------------- the main route

    async def brain_dump(
        self,
        account_id: int,
        *,
        entry_id: int,
        entry_text: str,
        profile_id: int | None = None,
        profile_name: str = "",
        person_id: int | None = None,
        want_reflection: bool = False,
        occurred_on: str | None = None,
    ) -> BrainDumpResult:
        self.store_account = account_id
        self.check_budget(account_id)

        run_id = self.store.start_run(account_id, "brain_dump")
        result = BrainDumpResult(run_id=run_id)
        seq = 0

        # --- Narrative and Safety, together, on the raw text ---------------
        narrative_task = narrative_agent.run(
            self.model, self.info, entry_text, occurred_on=occurred_on
        )
        safety_task = safety_agent.run(self.model, self.info, entry_text)
        narrative_step, safety_step = await asyncio.gather(narrative_task, safety_task)

        for step in (narrative_step, safety_step):
            seq += 1
            result.steps.append(step)
            self._record(run_id, seq, step)
            if not step.ok:
                result.errors.append(f"{step.agent}: {step.error}")

        result.narrative = narrative_step.output if narrative_step.ok else None
        result.safety = safety_step.output if safety_step.ok else None

        # --- the safety halt ------------------------------------------------
        if result.safety and result.safety.concern_detected:
            self.store.log_safety_event(
                account_id=account_id, entry_id=entry_id, run_id=run_id,
                trigger="narrative_screen",
                category=result.safety.category,
                concern_level=result.safety.concern_level,
                action=result.safety.suggested_action,
                detail=result.safety.rationale,
            )
            result.resources = safety_agent.resources_to_offer(
                self.store, account_id, result.safety
            )
            if result.resources:
                self.store.record_resource_offer(
                    account_id, [r["id"] for r in result.resources],
                    result.safety.concern_level,
                )
            if result.safety.suggested_action == "halt_and_route":
                result.halted = True
                result.halt_reason = result.safety.rationale
                result.status = "safety_halt"
                self.store.finish_run(run_id, "safety_halt", result.halt_reason)
                return result

        if result.narrative is None:
            result.status = "failed"
            self.store.finish_run(run_id, "failed", "; ".join(result.errors))
            return result

        # --- persist the narrative -----------------------------------------
        observation_ids = self.store.save_observations(
            account_id, entry_id,
            [o.model_dump() for o in result.narrative.observations],
            run_id=run_id,
        )

        # --- Evidence ------------------------------------------------------
        if profile_id is not None:
            criteria_rows = self.store.list_profile_criteria(profile_id)
            evidence_step = await evidence_agent.run(
                self.model, self.info, profile_name=profile_name,
                criteria=criteria_rows, narrative=result.narrative,
            )
            seq += 1
            result.steps.append(evidence_step)
            self._record(run_id, seq, evidence_step)
            if evidence_step.ok:
                result.evidence = evidence_step.output
                self._persist_mappings(
                    account_id, entry_id, profile_id, person_id,
                    result.evidence, observation_ids, run_id,
                )
            else:
                result.errors.append(f"evidence: {evidence_step.error}")

        # --- Reasoning, only when there is something to interrogate --------
        if reasoning_agent.needs_interrogation(
            entry_text, result.narrative.user_conclusions
        ) and len(result.steps) < MAX_AGENT_CALLS:
            reasoning_step = await reasoning_agent.run(
                self.model, self.info,
                profile_name=profile_name,
                criteria=self.store.list_profile_criteria(profile_id) if profile_id else [],
                narrative=result.narrative,
                evidence=result.evidence,
                entries=self.store.list_entries(account_id, limit=20),
                decisions=self.store.list_decisions(account_id, limit=10),
                entry_text=entry_text,
            )
            seq += 1
            result.steps.append(reasoning_step)
            self._record(run_id, seq, reasoning_step)
            if reasoning_step.ok:
                result.reasoning = reasoning_step.output
                self._persist_reasoning(
                    account_id, entry_id, profile_id, person_id, result.reasoning, run_id,
                )
            else:
                result.errors.append(f"reasoning: {reasoning_step.error}")

        # --- Reflection, only when wanted ----------------------------------
        probe_due = False
        postponements = 0
        if person_id is not None:
            postponements = self.store.count_postponements(account_id)
            probe_due = self.store.should_probe_postponement(account_id)

        if (want_reflection or probe_due) and len(result.steps) < MAX_AGENT_CALLS:
            reflection_step = await reflection_agent.run(
                self.model, self.info,
                entry_text=entry_text,
                reasoning=result.reasoning,
                postponement_count=postponements,
                probe_due=probe_due,
                safety_fired=bool(result.safety and result.safety.concern_detected),
            )
            seq += 1
            result.steps.append(reflection_step)
            self._record(run_id, seq, reflection_step)
            if reflection_step.ok:
                result.reflection = reflection_step.output
                self.store.save_reflection(
                    account_id,
                    question=result.reflection.question,
                    context=result.reflection.context,
                    tone_mode="clarity",
                    is_postponement_probe=result.reflection.is_postponement_probe,
                    run_id=run_id,
                )
            else:
                result.errors.append(f"reflection: {reflection_step.error}")

        result.status = "ok" if not result.errors else "partial"
        self.store.finish_run(run_id, result.status, "; ".join(result.errors) or None)
        return result

    # ------------------------------------------------------------- persistence

    def _persist_mappings(self, account_id, entry_id, profile_id, person_id,
                          evidence, observation_ids, run_id) -> None:
        """Agent-proposed mappings land as `pending`. The user accepts, rejects or edits.

        Note what is absent: no call to ``set_assessment``. An agent cannot move a
        criterion's status from here, whatever it mapped.
        """
        for m in evidence.mappings:
            obs_id = (observation_ids[m.observation_index]
                      if 0 <= m.observation_index < len(observation_ids) else None)
            try:
                self.store.link_evidence(
                    account_id, entry_id=entry_id, criterion_id=m.criterion_id,
                    relation=m.relation, profile_id=profile_id,
                    observation_id=obs_id, person_id=person_id,
                    rationale=m.rationale, source_level=m.source_level,
                    research_ref=m.research_ref, proposed_by="agent", run_id=run_id,
                )
            except Exception:
                continue  # a bad mapping is dropped, not written

    def _persist_reasoning(self, account_id, entry_id, profile_id, person_id,
                           reasoning: ReasoningOutput, run_id) -> None:
        for q in reasoning.interrogations:
            self.store.save_interrogation(
                account_id, entry_id=entry_id, claim=q.claim,
                claim_valence=q.claim_valence, gap_kind=q.gap_kind,
                question=q.question, materiality=q.materiality, run_id=run_id,
            )
        for p in reasoning.patterns:
            evidence_rows = (
                [{"entry_id": i} for i in p.supporting_entry_ids]
                + [{"entry_id": i, "stance": "contradicts"}
                   for i in p.contradicting_entry_ids]
            )
            if not evidence_rows:
                continue
            try:
                self.store.save_pattern(
                    account_id, profile_id=profile_id,
                    kind=p.kind, statement=p.statement,
                    evidence=evidence_rows, criterion_id=p.criterion_id,
                    evidence_strength=p.evidence_strength, gap_note=p.gap_note,
                    uncertainties=p.uncertainties, alternatives=p.alternatives,
                    run_id=run_id,
                )
            except Exception:
                continue
        # Proposals are suggestions and stay inert until the user acts on them.
        if person_id is not None and profile_id is not None:
            for prop in reasoning.proposals:
                try:
                    self.store.propose_assessment(
                        account_id, profile_id, prop.criterion_id, person_id,
                        prop.proposed_status, prop.rationale, run_id=run_id,
                    )
                except Exception:
                    continue

    # ------------------------------------------------------------- criteria route

    async def clarify_criterion(self, account_id: int, **kw) -> AgentResult:
        """One call. Off the brain-dump path, so it costs nothing on a journal entry."""
        self.store_account = account_id
        self.check_budget(account_id)
        run_id = self.store.start_run(account_id, "criteria")
        # The store is handed in so the agent gets its research tool. It reads only
        # verified knowledge-base rows; it has no access to user data.
        step = await criteria_agent.run(self.model, self.info, store=self.store, **kw)
        self._record(run_id, 1, step)
        self.store.finish_run(run_id, "ok" if step.ok else "failed", step.error)
        return step
