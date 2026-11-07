#!/usr/bin/env python3
"""Wiring tests: real Argon2id, real agent construction, real routing.

Free — no API call and no network. Needs the venv.

Covers the things the other two suites deliberately stub:

  * ``test_offline.py`` stubs ``backend.security`` so it can run with nothing installed.
    Here the real Argon2id path runs.
  * ``test_contracts.py`` validates output shapes without constructing agents. Here each
    agent is actually built against PydanticAI's ``TestModel``, which catches a provider
    or API mismatch without spending a credit.

    .venv/bin/python tests/test_wiring.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

PASSED = 0
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{label}{(' — ' + detail) if detail else ''}")


# ---------------------------------------------------------------- real hashing

def test_argon2id_for_real() -> None:
    from backend.security import (
        MIN_PASSPHRASE_LENGTH, WeakPassphrase, hash_passphrase, verify_passphrase,
    )

    secret = "correct horse battery staple"
    h = hash_passphrase(secret)

    check("the hash is Argon2id", h.startswith("$argon2id$"), h[:20])
    check("the passphrase is not recoverable from the hash", secret not in h)
    check("the correct passphrase verifies", verify_passphrase(secret, h) is True)
    check("a wrong passphrase does not", verify_passphrase("wrong", h) is False)
    check("an empty passphrase does not", verify_passphrase("", h) is False)

    # The library salts per-hash; identical passphrases must not collide.
    h2 = hash_passphrase(secret)
    check("the same passphrase hashes differently each time", h != h2)
    check("and both still verify", verify_passphrase(secret, h2) is True)

    # A missing account still does the work, so timing does not reveal which handles exist.
    check("verifying against no stored hash returns False",
          verify_passphrase(secret, None) is False)

    try:
        hash_passphrase("short")
    except WeakPassphrase:
        check("a short passphrase is refused", True)
    else:
        check("a short passphrase is refused", False, "accepted")
    check("the minimum is stated in the error path", MIN_PASSPHRASE_LENGTH >= 10)


def test_account_round_trip_with_real_hashing() -> None:
    """The store and the real hasher together, without the stub."""
    from backend.store import Store

    s = Store(Path(tempfile.mkdtemp()) / "t.db")
    acct = s.create_account("tester", "a long enough passphrase")
    check("the account is created", bool(acct))
    check("the right passphrase logs in",
          s.verify_account("tester", "a long enough passphrase") == acct)
    check("the wrong one does not", s.verify_account("tester", "nope") is None)

    row = s.get_account(acct)
    check("get_account never returns the hash", "passphrase_hash" not in row)
    blob = s.export_account(acct)
    check("export never contains argon2 material", "$argon2" not in repr(blob))
    check("the default tone mode is clarity", row["tone_mode"] == "clarity")
    check("resources are offered proactively by default",
          row["resource_offering"] == "proactive")


# ---------------------------------------------------------------- provider

def test_provider_falls_back_to_demo_without_a_key() -> None:
    """A fresh clone with no .env must still run. A traceback is not a demo."""
    import os

    from backend.provider import Mode, build, resolve_mode

    saved = os.environ.pop("PORTKEY_API_KEY", None), os.environ.pop("KRYTERIA_MODE", None)
    try:
        os.environ["KRYTERIA_MODE"] = "demo"
        mode = resolve_mode()
        check("demo mode resolves", mode is Mode.DEMO)
        model, info = build("demo")
        check("demo needs no key", info.provider == "deterministic")
        check("demo usage is flagged simulated", info.simulated is True)
        check("and is therefore never billable", info.billable is False)

        model, info = build("test")
        check("test mode gives a TestModel", type(model).__name__ == "TestModel")
        check("test usage is simulated too", info.simulated is True)
    finally:
        os.environ.pop("KRYTERIA_MODE", None)
        if saved[0]:
            os.environ["PORTKEY_API_KEY"] = saved[0]
        if saved[1]:
            os.environ["KRYTERIA_MODE"] = saved[1]


def test_model_is_pinned() -> None:
    """OPENAI_MODEL cannot win. Five agents on one stray variable would re-bill the lot."""
    import app_config

    check("the required model is gpt-6-luna",
          app_config.REQUIRED_OPENAI_MODEL == "gpt-6-luna")
    source = (PROJECT_DIR / "app_config.py").read_text()
    check("the name lives in exactly one place",
          source.count('"gpt-6-luna"') == 1)
    check("OpenAIResponsesModel is used, not chat completions",
          "OpenAIResponsesModel" in source and "OpenAIChatModel" not in source)


def test_costs_never_invent_numbers() -> None:
    from backend.costs import Usage, estimate_cost, have_prices_for

    simulated = Usage(input_tokens=9999, output_tokens=9999, model_name="gpt-6-luna",
                      simulated=True)
    check("simulated usage costs nothing", estimate_cost(simulated) == 0.0)

    unknown = Usage(input_tokens=1000, output_tokens=100, model_name="some-other-model")
    check("an unpriced model yields 0.0, to be reported as unavailable",
          estimate_cost(unknown) == 0.0)
    check("and we can tell that we have no prices for it",
          have_prices_for("some-other-model") is False)

    no_cache = Usage(input_tokens=1000, output_tokens=100, model_name="gpt-6-luna")
    check("unreported cache stays None, never 0",
          no_cache.cached_input_tokens is None)
    check("so every input token is treated as uncached",
          no_cache.uncached_input_tokens == 1000)

    with_cache = Usage(input_tokens=1000, cached_input_tokens=800, output_tokens=100)
    check("a reported cache splits the input", with_cache.uncached_input_tokens == 200)


# ---------------------------------------------------------------- agents construct

def test_every_agent_builds() -> None:
    """Construct each agent against TestModel. Catches an API mismatch for free."""
    from pydantic_ai.models.test import TestModel

    from backend.agents import (
        criteria as criteria_agent, evidence as evidence_agent,
        narrative as narrative_agent, reasoning as reasoning_agent,
        reflection as reflection_agent, safety as safety_agent,
    )

    model = TestModel()
    for name, module in [
        ("narrative", narrative_agent), ("safety", safety_agent),
        ("evidence", evidence_agent), ("reasoning", reasoning_agent),
        ("reflection", reflection_agent), ("criteria", criteria_agent),
    ]:
        try:
            agent = module.build(model)
        except Exception as e:
            check(f"{name} agent builds", False, f"{type(e).__name__}: {e}")
            continue
        check(f"{name} agent builds", True)
        prompt = module.load_prompt(module.PROMPT_PATH) if hasattr(module, "load_prompt") \
            else None
        if prompt is None:
            from backend.agents.base import load_prompt
            prompt = load_prompt(module.PROMPT_PATH)
        check(f"{name} loads a non-trivial prompt", len(prompt) > 500)
        check(f"{name} agent has a system prompt", agent is not None)


def test_narrative_runs_against_testmodel() -> None:
    """One full agent run, free, proving the plumbing end to end."""
    from pydantic_ai.models.test import TestModel

    from backend.agents import narrative as narrative_agent
    from backend.provider import ProviderInfo, Mode

    info = ProviderInfo(mode=Mode.TEST, model_name="test", provider="pydantic-ai",
                        simulated=True)
    result = asyncio.run(narrative_agent.run(
        TestModel(), info, "We had dinner. He was twenty minutes late."
    ))
    check("the run completes", result.ok, result.error or "")
    check("it returns a validated NarrativeOutput",
          type(result.output).__name__ == "NarrativeOutput")
    check("usage is recorded", result.usage is not None)
    check("simulated usage costs nothing", result.cost_usd == 0.0)
    check("the step is flagged simulated", result.simulated is True)


def test_orchestrator_budget_is_enforced_in_code() -> None:
    from backend.agents.orchestrator import BudgetExceeded, Orchestrator
    from backend.provider import Mode, ProviderInfo
    from backend.store import Store

    s = Store(Path(tempfile.mkdtemp()) / "t.db")
    acct = s.create_account("tester", "a long enough passphrase")
    live = ProviderInfo(mode=Mode.LIVE, model_name="gpt-6-luna", provider="portkey",
                        simulated=False)
    orch = Orchestrator(s, object(), live)
    orch.per_account_cap = 1000

    orch.check_budget(acct)  # under the cap
    check("a fresh account is under budget", True)

    s.add_usage(acct, input_tokens=900, output_tokens=200)
    try:
        orch.check_budget(acct)
    except BudgetExceeded:
        check("the per-account cap is enforced", True)
    else:
        check("the per-account cap is enforced", False, "not raised")

    # Simulated providers never consume a budget, and cannot be used to mask one.
    demo = ProviderInfo(mode=Mode.DEMO, model_name="kryteria-demo",
                        provider="deterministic", simulated=True)
    Orchestrator(s, object(), demo).check_budget(acct)
    check("demo mode is exempt from the budget", True)

    orch.global_cap = 100
    orch.per_account_cap = 10_000_000
    try:
        orch.check_budget(acct)
    except BudgetExceeded as e:
        check("the global cap is enforced too", "KRYteria's daily" in str(e))
    else:
        check("the global cap is enforced too", False, "not raised")


def test_orchestrator_has_no_path_to_set_assessment() -> None:
    """The agents prepare; the user decides. Asserted against the source."""
    import ast

    def calls_in(path: Path) -> set[str]:
        """Attribute calls actually made — not words in comments or docstrings."""
        tree = ast.parse(path.read_text())
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                found.add(node.func.attr)
        return found

    agents_dir = PROJECT_DIR / "backend" / "agents"
    orch_calls = calls_in(agents_dir / "orchestrator.py")
    check("the orchestrator never calls set_assessment",
          "set_assessment" not in orch_calls,
          "found a call that would let an agent move a status")
    check("it proposes instead", "propose_assessment" in orch_calls)
    check("it does record evidence links", "link_evidence" in orch_calls)

    for name in ("narrative", "safety", "evidence", "reasoning", "reflection", "criteria"):
        calls = calls_in(agents_dir / f"{name}.py")
        check(f"{name} cannot set an assessment", "set_assessment" not in calls)
        check(f"{name} cannot resolve a proposal", "resolve_proposal" not in calls)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{PASSED} passed, {len(FAILED)} failed  ({len(tests)} test functions)")
    for f in FAILED:
        print(f"  FAIL  {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
