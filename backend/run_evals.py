"""Run the evaluation packs and the A/B comparison.

    .venv/bin/python -m backend.run_evals list
    .venv/bin/python -m backend.run_evals safety                      # demo: wiring only
    .venv/bin/python -m backend.run_evals all --mode live --yes-spend-credits
    .venv/bin/python -m backend.run_evals ab --mode live --yes-spend-credits

Demo mode is the default and is free. It proves the harness runs; it grades nothing about
the real agents, and every artefact it writes says so on its first line.

Live mode costs money and refuses to start without ``--yes-spend-credits``, after
printing the call count. Christine's Portkey budget is tight and an accidental live run
has already happened once on this project.
"""

from __future__ import annotations

import argparse
import sys

from .evals import ab, report, runner

#: Measured from the 2026-11-09 accidental live run, plus the routing rules. Narrative
#: and Safety always run; Evidence whenever a profile is attached; Reasoning when there
#: is something to interrogate, which these cases are built to trigger.
CALLS_PER_CASE = 4
BASELINE_CALLS_PER_SCENARIO = 1


def _estimate(n_cases: int, *, ab_scenarios: int = 0) -> int:
    return n_cases * CALLS_PER_CASE + ab_scenarios * (CALLS_PER_CASE + 1)


def _confirm_live(args, n_calls: int) -> None:
    if args.mode != "live":
        return
    print(f"\n  LIVE MODE — this will make roughly {n_calls} real gpt-6-luna calls.")
    print("  Measured averages per call: ~1.4k input, ~0.4k output tokens.\n")
    if not args.yes_spend_credits:
        print("  Refusing to start. Re-run with --yes-spend-credits if that is what "
              "you want.")
        raise SystemExit(2)


def cmd_list(args) -> None:
    for name in runner.PACKS:
        pack = runner.load_pack(name)
        auto = sum(1 for c in pack["cases"] for k in c["checks"] if k["check"] != "manual")
        man = sum(1 for c in pack["cases"] for k in c["checks"] if k["check"] == "manual")
        print(f"{name:<10} {len(pack['cases']):>3} cases · {auto:>3} automatic checks "
              f"· {man:>3} needing a person")
    scenarios = ab.load_scenarios()["scenarios"]
    print(f"{'ab':<10} {len(scenarios):>3} scenarios · "
          f"{sum(len(s['dimensions']) for s in scenarios):>3} dimensions, prose-only")
    print(f"\nA full live run is about {_estimate(31, ab_scenarios=5)} model calls.")


def _run_pack(name: str, args, *, stem: str, title: str) -> int:
    rep = runner.run_pack_sync(name, mode=args.mode, only=args.only or None)
    json_path, md_path = report.write(rep, stem=stem, title=title)
    agg = runner.totals(rep)
    print(f"\n{name}: {agg['cases']['pass']} passed · {agg['cases']['fail']} FAILED · "
          f"{agg['cases']['needs_review']} need review · {agg['cases']['error']} errored")
    print(f"  {json_path.relative_to(report.PROJECT_DIR)}")
    print(f"  {md_path.relative_to(report.PROJECT_DIR)}")
    if rep["simulated"]:
        print("  (demo mode — these results are not evidence of anything)")
    return agg["cases"]["fail"] + agg["cases"]["error"]


def cmd_safety(args) -> int:
    _confirm_live(args, _estimate(18))
    return _run_pack("safety", args, stem="safety_results",
                     title="KRYteria safety evaluations")


def cmd_reasoning(args) -> int:
    _confirm_live(args, _estimate(13))
    return _run_pack("reasoning", args, stem="reasoning_results",
                     title="KRYteria adversarial reasoning evaluations")


def cmd_ab(args) -> int:
    scenarios = ab.load_scenarios()["scenarios"]
    _confirm_live(args, _estimate(0, ab_scenarios=len(scenarios)))
    rep = ab.run_ab_sync(mode=args.mode, only=args.only or None)
    json_path, md_path = report.write_ab(rep)
    print(f"\nA/B: {len(rep['scenarios'])} scenarios")
    for s in rep["scenarios"]:
        k, b = s["systems"]["kryteria"], s["systems"]["generic_chatbot"]
        print(f"  {s['id']:<22} KRYteria {k['passed']}  ·  chatbot {b['passed']}")
    print(f"  {json_path.relative_to(report.PROJECT_DIR)}")
    print(f"  {md_path.relative_to(report.PROJECT_DIR)}")
    if rep["simulated"]:
        print("  (demo mode — not a comparison)")
    return 0


def cmd_all(args) -> int:
    _confirm_live(args, _estimate(31, ab_scenarios=5))
    args.yes_spend_credits = True  # already confirmed once; do not ask three times
    bad = cmd_safety(args) + cmd_reasoning(args)
    cmd_ab(args)
    return bad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run_evals", description=__doc__)
    p.add_argument("command",
                   choices=["list", "safety", "reasoning", "ab", "all"])
    p.add_argument("--mode", default="demo", choices=["demo", "test", "live"],
                   help="demo (free, proves wiring) or live (real calls, real evidence)")
    p.add_argument("--only", nargs="*", metavar="ID",
                   help="run only these case or scenario ids")
    p.add_argument("--yes-spend-credits", action="store_true",
                   help="required for --mode live")
    args = p.parse_args(argv)

    if args.command == "list":
        cmd_list(args)
        return 0
    return {"safety": cmd_safety, "reasoning": cmd_reasoning,
            "ab": cmd_ab, "all": cmd_all}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
