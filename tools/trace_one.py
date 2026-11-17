#!/usr/bin/env python3
"""Run ONE demo entry live and print the per-agent trace.

The report's "one real run, traced" table needs figures per agent — input, output,
latency — and `run_character_analysis` only reports per-entry totals. Rather than
estimate a breakdown from a total, this runs a single entry and prints what each agent
actually cost.

    .venv/bin/python tools/trace_one.py jane-money-3 --yes-spend-credits

Needs a real terminal, not the sandboxed shell: the key lives in a .env the sandbox
refuses to read, so the provider resolves to demo mode there and the numbers would be
simulated.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.orchestrator import Orchestrator          # noqa: E402
from backend.provider import Mode, build                      # noqa: E402
from backend.seed_characters import load_character_files, seed  # noqa: E402
from backend.store import Store                               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key", help="entry key, e.g. jane-money-3")
    ap.add_argument("--yes-spend-credits", action="store_true")
    args = ap.parse_args()

    char = entry = None
    for c in load_character_files():
        for e in c.get("entries", []):
            if e["key"] == args.key:
                char, entry = c, e
    if entry is None:
        print(f"No entry with key {args.key!r}", file=sys.stderr)
        return 1

    reflection = bool(entry.get("analyze_reflection"))
    print(f"{char['display_name']} · {args.key} · "
          f"{'5' if reflection else 'up to 4'} agents\n")
    if not args.yes_spend_credits:
        print("  Estimate only. Re-run with --yes-spend-credits.")
        return 0

    model, info = build()
    if info.mode is not Mode.LIVE:
        print(f"Provider is in {info.mode.value} mode. A simulated trace is not a trace.",
              file=sys.stderr)
        return 1

    store = Store(Path(tempfile.mkdtemp()) / "trace.db")
    accounts = seed(store, reset=True, skip_generated=True)
    account_id = accounts[char["handle"]]

    row = next(e for e in store.list_entries(account_id)
               if (e.get("body") or "")[:60] == entry["body"][:60])
    profile_id = next(
        (p["id"] for p in store.list_profiles(account_id)
         if p["name"] == entry.get("analyze_profile")), None)

    orch = Orchestrator(store, model, info)
    res = asyncio.run(orch.brain_dump(
        account_id, entry_id=row["id"], entry_text=entry["body"],
        profile_id=profile_id, profile_name=entry.get("analyze_profile", ""),
        person_id=row.get("person_id"), want_reflection=reflection,
        occurred_on=row.get("occurred_on"),
    ))

    print(f"{'agent':<12}{'input':>9}{'output':>9}{'latency':>10}")
    print("-" * 40)
    for step in res.steps:
        u = step.usage
        tin = getattr(u, "input_tokens", 0) if u else 0
        tout = getattr(u, "output_tokens", 0) if u else 0
        print(f"{step.agent:<12}{tin:>9,}{tout:>9,}{step.latency_ms / 1000:>9.1f}s"
              + ("" if step.ok else f"   ERROR: {step.error}"))
    print("-" * 40)
    print(f"{'TOTAL':<12}{res.input_tokens:>9,}{res.output_tokens:>9,}"
          f"{'':>10}  ${res.cost_usd:.5f}  ({res.model_calls} calls)")

    if res.errors:
        print(f"\nerrors: {res.errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
