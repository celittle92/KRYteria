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
    ap.add_argument("key", help="entry key, e.g. jane-money-3 — or --text-file")
    ap.add_argument("--yes-spend-credits", action="store_true")
    ap.add_argument("--text-file", help=(
        "Run this text instead of a seeded entry. For checking a prompt change against "
        "something a person actually wrote: it creates one entry in a throwaway database "
        "and touches no demo data."))
    ap.add_argument("--as", dest="handle", help="character handle, with --text-file")
    ap.add_argument("--profile", help="profile name, with --text-file")
    ap.add_argument("--reflection", action="store_true",
                    help="also run Reflection, with --text-file")
    ap.add_argument("--dry-run", action="store_true", help=(
        "Allow the simulated provider, to prove the wiring without spending anything. "
        "The output is invented and is never evidence."))
    ap.add_argument("--show", action="store_true", help=(
        "Print what the run DECIDED — observations and whose conduct each describes, "
        "every mapping, the unsettled notes, the questions and the reflection. The token "
        "table says what a run cost; this says whether it was any good."))
    args = ap.parse_args()

    char = entry = None
    if args.text_file:
        if not (args.handle and args.profile):
            print("--text-file needs --as HANDLE and --profile NAME", file=sys.stderr)
            return 1
        body = Path(args.text_file).read_text(encoding="utf-8").strip()
        char = next((c for c in load_character_files()
                     if c.get("handle") == args.handle), None)
        if char is None:
            print(f"No character with handle {args.handle!r}", file=sys.stderr)
            return 1
        entry = {"key": "(from --text-file)", "body": body,
                 "analyze_profile": args.profile,
                 "analyze_reflection": args.reflection}
    else:
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
        if not args.dry_run:
            print(f"Provider is in {info.mode.value} mode. A simulated trace is not a "
                  "trace.", file=sys.stderr)
            return 1
        # Proving the plumbing before paying for it. Every figure below is invented by
        # the deterministic provider, so this is a wiring check and NEVER evidence — the
        # same line this project draws everywhere else between demo output and a result.
        print("=" * 72)
        print("  DRY RUN — simulated provider. The wiring is real; the output is not.")
        print("=" * 72 + "\n")

    store = Store(Path(tempfile.mkdtemp()) / "trace.db")
    accounts = seed(store, reset=True, skip_generated=True)
    account_id = accounts[char["handle"]]

    if args.text_file:
        # A new entry in a throwaway database seeded from the character files, so the
        # text is judged against that character's real criteria and real history without
        # anything being written into the committed demo data.
        domain_id = next(iter(store.list_domains(account_id)), {}).get("id")
        row = {"id": store.create_entry(account_id, domain_id, body=entry["body"]),
               "person_id": None, "occurred_on": None}
    else:
        row = next(e for e in store.list_entries(account_id)
                   if (e.get("body") or "")[:60] == entry["body"][:60])
    profile_id = next(
        (p["id"] for p in store.list_profiles(account_id)
         if p["name"] == entry.get("analyze_profile")), None)
    if profile_id is None:
        print(f"No profile named {entry.get('analyze_profile')!r} for "
              f"{char['handle']}. Available: "
              f"{[p['name'] for p in store.list_profiles(account_id)]}", file=sys.stderr)
        return 1

    orch = Orchestrator(store, model, info)
    res = asyncio.run(orch.brain_dump(
        account_id, entry_id=row["id"], entry_text=entry["body"],
        profile_id=profile_id, profile_name=entry.get("analyze_profile", ""),
        person_id=row.get("person_id"), want_reflection=reflection,
        occurred_on=row.get("occurred_on"),
    ))

    # The cached column exists because it was missing once and that cost a real number.
    # The §4 run's recorded cost sits $0.00046 below what the uncached arithmetic gives,
    # which implies about 5,140 cached input tokens — so the provider reported them, the
    # cost already reflects them, and nothing wrote the figure down. "not reported" and
    # "not recorded" are different admissions and only one of them is ours.
    print(f"{'agent':<12}{'input':>9}{'cached':>9}{'output':>9}{'latency':>10}")
    print("-" * 49)
    cached_total, any_cached = 0, False
    for step in res.steps:
        u = step.usage
        tin = getattr(u, "input_tokens", 0) if u else 0
        tout = getattr(u, "output_tokens", 0) if u else 0
        tcac = getattr(u, "cached_input_tokens", None) if u else None
        if tcac is not None:
            any_cached = True
            cached_total += tcac
        print(f"{step.agent:<12}{tin:>9,}{(f'{tcac:,}' if tcac is not None else '—'):>9}"
              f"{tout:>9,}{step.latency_ms / 1000:>9.1f}s"
              + ("" if step.ok else f"   ERROR: {step.error}"))
    print("-" * 49)
    print(f"{'TOTAL':<12}{res.input_tokens:>9,}"
          f"{(f'{cached_total:,}' if any_cached else '—'):>9}{res.output_tokens:>9,}"
          f"{'':>10}  ${res.cost_usd:.5f}  ({res.model_calls} calls)")
    if not any_cached:
        print("\nThe provider reported no cached-input count on any call in this run.\n"
              "That is recorded as unknown, never as zero.")

    if args.show:
        _show(res, store, account_id, profile_id)

    if res.errors:
        print(f"\nerrors: {res.errors}")
    return 0


def _show(res, store, account_id: int, profile_id: int | None) -> None:
    """What the run DECIDED, not what it cost.

    The token table answers "was this affordable". This answers "was it any good", which
    is the only question a prompt change can be judged on — and the reason it exists is
    that a page of mapping rows looked fine as a number and was wrong as a product.
    """
    names = {c["criterion_id"]: c["value"]
             for c in (store.list_profile_criteria(account_id, profile_id)
                       if profile_id else [])}

    if res.narrative:
        print("\n\nOBSERVATIONS — and whose conduct each describes")
        print("-" * 72)
        tally: dict[str, int] = {}
        for o in res.narrative.observations:
            about = getattr(o, "about", "unclear")
            tally[about] = tally.get(about, 0) + 1
            print(f"  [{about:>7}] {o.kind:<20} {o.text}")
        print(f"\n  {tally}")

    if res.evidence:
        print(f"\n\nMAPPINGS — {len(res.evidence.mappings)} of them")
        print("-" * 72)
        by_relation: dict[str, int] = {}
        for m in res.evidence.mappings:
            by_relation[m.relation] = by_relation.get(m.relation, 0) + 1
            print(f"  {m.relation:<15} {names.get(m.criterion_id, m.criterion_id)}")
            if m.rationale:
                print(f"                  {m.rationale}")
        print(f"\n  {by_relation}")
        print(f"  unmapped observations: {res.evidence.unmapped_observation_indexes}")
        if res.evidence.insufficient:
            print(f"\n  NOT SETTLED ({len(res.evidence.insufficient)}):")
            for n in res.evidence.insufficient:
                print(f"    {names.get(n.criterion_id, n.criterion_id)}: {n.why}")

    if res.reasoning:
        print("\n\nQUESTIONS")
        print("-" * 72)
        for q in res.reasoning.interrogations:
            print(f"  [{q.materiality}/{q.gap_kind}] {q.question}")
        for n in res.reasoning.cross_criterion:
            print(f"  (cross) {n.explanation}")

    if res.reflection:
        print("\n\nREFLECTION")
        print("-" * 72)
        print(f"  context:  {res.reflection.context}")
        print(f"  question: {res.reflection.question}")


if __name__ == "__main__":
    raise SystemExit(main())
