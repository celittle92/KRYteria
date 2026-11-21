"""Load the packs, run every case, grade the result.

The orchestrator is driven exactly as the API drives it. The harness does not reach past
it into individual agents, because routing is part of what is being graded: a case that
should never have called Reasoning fails differently from one that called it and reasoned
badly, and only the real route shows which happened.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import provider
from ..agents.orchestrator import Orchestrator
from ..store import Store
from . import checks as checks_mod
from .scenario import build_world, new_entry, seed_resources
from .transcript import Transcript, from_brain_dump

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
PACK_DIR = PROJECT_DIR / "tests" / "evals"

PACKS = {
    "safety": PACK_DIR / "safety_evals.json",
    "reasoning": PACK_DIR / "reasoning_evals.json",
}


class PackError(ValueError):
    """A pack is malformed in a way that would make its results meaningless."""


@dataclass
class CaseResult:
    pack: str
    case_id: str
    title: str
    user_input: str
    rows: list[dict] = field(default_factory=list)
    transcript: Transcript | None = None
    error: str | None = None

    @property
    def counts(self) -> dict[str, int]:
        out = {checks_mod.PASS: 0, checks_mod.FAIL: 0,
               checks_mod.REVIEW: 0, checks_mod.NA: 0}
        for r in self.rows:
            out[r["outcome"]] = out.get(r["outcome"], 0) + 1
        return out

    @property
    def verdict(self) -> str:
        if self.error:
            return "error"
        c = self.counts
        if c[checks_mod.FAIL]:
            return checks_mod.FAIL
        if c[checks_mod.REVIEW]:
            return checks_mod.REVIEW
        return checks_mod.PASS


def load_pack(name: str) -> dict:
    """Read a pack and refuse one whose cases cannot actually be graded."""
    path = PACKS[name]
    if not path.is_file():
        raise PackError(f"Missing eval pack: {path}")
    pack = json.loads(path.read_text(encoding="utf-8"))

    ungradable = []
    for case in pack.get("cases", []):
        if not case.get("checks"):
            ungradable.append(case.get("id", "<no id>"))
            continue
        for spec in case["checks"]:
            if spec.get("check") not in checks_mod._REGISTRY:
                raise PackError(
                    f"{name}/{case['id']}: unknown check {spec.get('check')!r}. "
                    f"Known: {', '.join(checks_mod.known_checks())}"
                )
            # A `prose_lacks` needle drawn from the user's own sentence is FINE, and
            # deliberately not refused here. It was, for about ten minutes on
            # 2026-11-20, after `saf-cooldown-01` failed on `we said we'd leave this` —
            # a phrase lifted verbatim out of that case's own `user_input`. The suite
            # refused the whole reasoning pack a moment later over `not his fault` in
            # `exc-02`, which is the same shape and an entirely legitimate check.
            #
            # That is the point: with `transcript._is_quoted` in place, a needle taken
            # from the user is still meaningful. Quoting her is exempt; restating her
            # claim unquoted, in the system's own voice, is precisely the failure mode
            # `exc-02` exists to catch. A load-time refusal would have thrown away a
            # real check to fix a grader bug that was already fixed elsewhere.
    if ungradable:
        raise PackError(
            f"{name}: {len(ungradable)} case(s) carry no `checks` array and would be "
            f"silently skipped: {', '.join(ungradable)}. A case nobody can run is the "
            "state this harness exists to end — give it checks, or a single "
            '{"check": "manual", "says": "..."} if it is genuinely prose-level.'
        )
    return pack


def _grade(transcript: Transcript, case: dict) -> list[dict]:
    return [checks_mod.run_check(transcript, spec) for spec in case["checks"]]


async def _run_one(store: Store, model: Any, info: Any, pack_name: str,
                   case: dict) -> CaseResult:
    result = CaseResult(
        pack=pack_name, case_id=case["id"],
        title=case.get("failure_mode") or case.get("category") or "",
        user_input=case["user_input"],
    )
    try:
        world = build_world(store, case)
        entry_id = new_entry(store, world, case["user_input"])
        orch = Orchestrator(store, model, info)
        dump = await orch.brain_dump(
            world.account_id,
            entry_id=entry_id,
            entry_text=case["user_input"],
            profile_id=world.profile_id,
            profile_name=world.profile_name,
            person_id=world.person_id,
            want_reflection=bool(case.get("want_reflection")),
        )
        events = [dict(e) for e in store.list_safety_events(world.account_id)]
        result.transcript = from_brain_dump(dump, world.names, safety_events=events)
        result.rows = _grade(result.transcript, case)
    except Exception as exc:  # a broken case must not take the whole run down
        result.error = f"{type(exc).__name__}: {exc}"
    return result


async def run_pack(pack_name: str, *, mode: str, only: list[str] | None = None,
                   db_path: Path | None = None) -> dict:
    """Run one pack end to end and return a report-shaped dict."""
    pack = load_pack(pack_name)
    cases = pack["cases"]
    if only:
        wanted = set(only)
        cases = [c for c in cases if c["id"] in wanted]

    model, info = provider.build(mode)
    db = db_path or Path(tempfile.mkdtemp()) / f"evals_{pack_name}_{time.time()}.db"
    store = Store(db)
    seed_resources(store)

    started = time.time()
    results: list[CaseResult] = []
    for case in cases:
        results.append(await _run_one(store, model, info, pack_name, case))

    return {
        "pack": pack_name,
        "pack_version": pack.get("version"),
        "mode": info.mode.value,
        "model": info.model_name,
        "simulated": info.simulated,
        "evidence_value": "none" if info.simulated else "real",
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "duration_s": round(time.time() - started, 2),
        "cases": results,
        "universal_must_not": pack.get("universal_must_not", []),
        "failure_modes": pack.get("failure_modes", {}),
    }


def run_pack_sync(pack_name: str, **kw) -> dict:
    return asyncio.run(run_pack(pack_name, **kw))


def totals(report: dict) -> dict:
    agg = {checks_mod.PASS: 0, checks_mod.FAIL: 0,
           checks_mod.REVIEW: 0, checks_mod.NA: 0}
    verdicts = {checks_mod.PASS: 0, checks_mod.FAIL: 0,
                checks_mod.REVIEW: 0, "error": 0}
    for case in report["cases"]:
        for k, v in case.counts.items():
            agg[k] = agg.get(k, 0) + v
        verdicts[case.verdict] = verdicts.get(case.verdict, 0) + 1
    return {"checks": agg, "cases": verdicts, "total_cases": len(report["cases"])}
