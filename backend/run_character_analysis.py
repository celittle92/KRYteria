"""Run the real agent pipeline over the demo's proof-point entries, once, and keep it.

Why this exists
---------------
The nine characters' ordinary entries carry observations and evidence written by hand.
The entries that demonstrate the product's actual reasoning — the shared date night, the
postponement loop, the counter-evidence, the safety case — must not. Fixture text that
*looks* like agent output proves nothing, and a demo whose centrepiece is invented
analysis is a demo of nothing.

So those entries are flagged ``"analyze": true`` in the character files and carry no
seeded analysis at all. This script runs them through the same orchestrator the
application uses, and then **writes what came back into the character JSON**.

That last step is the point. The hosted deployment rebuilds its database from the
character files on every boot, so analysis living only in a database would vanish at the
next restart — and re-running the agents on each boot would spend real money every time
the free instance recycles. Generated once, frozen, and committed.

Everything written back carries provenance: which model produced it, when, and the run
id. Nobody reading the demo later has to guess which parts a model wrote.

    .venv/bin/python -m backend.run_character_analysis              # estimate only
    .venv/bin/python -m backend.run_character_analysis --yes-spend-credits
    .venv/bin/python -m backend.run_character_analysis --only cat-datenight
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

from .agents.orchestrator import Orchestrator
from .provider import Mode, build
from .seed_characters import CHARACTERS_DIR, load_character_files, seed
from .store import Store

REPORT_PATH = Path(__file__).resolve().parent.parent / "output" / "character_analysis.md"

#: Ordinary entry is Narrative + Safety + Evidence. Reasoning runs whenever the narrative
#: extracted a stated conclusion, which is most of these — they were chosen for being
#: entries where somebody concluded something. Reflection only where asked for.
CALLS_PER_ENTRY = 4


def flagged() -> list[tuple[dict, dict]]:
    """Every (character, entry) pair marked for live analysis."""
    out = []
    for char in load_character_files():
        for entry in char.get("entries", []):
            if entry.get("analyze"):
                out.append((char, entry))
    return out


def estimate(pairs: list[tuple[dict, dict]]) -> int:
    reflections = sum(1 for _, e in pairs if e.get("analyze_reflection"))
    return len(pairs) * CALLS_PER_ENTRY + reflections


async def analyse(store: Store, accounts: dict[str, int], pairs, model, info) -> list[dict]:
    orch = Orchestrator(store, model, info)
    results = []
    for char, entry in pairs:
        account_id = accounts[char["handle"]]
        entry_row = next(
            e for e in store.list_entries(account_id)
            if (e.get("body") or "")[:60] == entry["body"][:60]
        )
        profile_id = None
        if entry.get("analyze_profile"):
            profile_id = next(
                p["id"] for p in store.list_profiles(account_id)
                if p["name"] == entry["analyze_profile"]
            )
        person_id = entry_row.get("person_id")

        print(f"  {char['display_name']:10} {entry['key']:20} ", end="", flush=True)
        res = await orch.brain_dump(
            account_id,
            entry_id=entry_row["id"],
            entry_text=entry["body"],
            profile_id=profile_id,
            profile_name=entry.get("analyze_profile", ""),
            person_id=person_id,
            want_reflection=bool(entry.get("analyze_reflection")),
            occurred_on=entry_row.get("occurred_on"),
        )
        flag = "HALTED" if getattr(res, "halted", False) else "ok"
        print(f"{res.model_calls:2} calls  ${res.cost_usd:.5f}  {flag}"
              + (f"  ERRORS: {res.errors}" if res.errors else ""))
        results.append({
            "handle": char["handle"], "name": char["display_name"],
            "key": entry["key"], "entry_id": entry_row["id"],
            "run_id": res.run_id, "result": res,
        })
    return results


def harvest(db: Path, results: list[dict]) -> dict[str, dict]:
    """Read back what the agents persisted, keyed by entry key."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    out: dict[str, dict] = {}
    for r in results:
        eid = r["entry_id"]
        obs = [dict(x) for x in conn.execute(
            "SELECT kind, text, certainty, hedge FROM observations WHERE entry_id=?",
            (eid,))]
        ev = [dict(x) for x in conn.execute(
            "SELECT c.value AS criterion_value, e.relation, e.rationale, e.source_level "
            "FROM evidence_links e JOIN criteria c ON c.id = e.criterion_id "
            "WHERE e.entry_id=?", (eid,))]
        qs = [dict(x) for x in conn.execute(
            "SELECT claim, gap_kind, question, claim_valence, materiality "
            "FROM interrogations WHERE entry_id=?", (eid,))]
        themes = [x[0] for x in conn.execute(
            "SELECT theme_id FROM entry_themes WHERE entry_id=?", (eid,))]
        safety = [dict(x) for x in conn.execute(
            "SELECT category, concern_level, trigger, action, detail "
            "FROM safety_events WHERE entry_id=?", (eid,))]
        out[r["key"]] = {"observations": obs, "evidence": ev, "interrogations": qs,
                         "themes": themes, "safety": safety}
    return out


def write_back(harvested: dict[str, dict], info, run_date: str) -> int:
    """Freeze the generated analysis into the character files.

    Written under a ``generated`` key rather than merged into the hand-written fields, so
    that what a model produced stays distinguishable from what a person wrote. The
    specification is explicit that the audience must be able to tell those apart.
    """
    touched = 0
    for path in sorted(CHARACTERS_DIR.glob("*.json")):
        char = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for entry in char.get("entries", []):
            got = harvested.get(entry["key"])
            if not got:
                continue
            entry["generated"] = {
                "_comment": ("Produced by the agent pipeline, not written by hand. "
                             "Frozen so the hosted deployment — which rebuilds from "
                             "these files on every boot — shows real output without "
                             "spending credits on each restart."),
                "by": info.model_name,
                "on": run_date,
                **got,
            }
            changed = True
        if changed:
            path.write_text(json.dumps(char, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
            touched += 1
    return touched


def report(results: list[dict], harvested: dict, info, run_date: str) -> None:
    calls = sum(r["result"].model_calls for r in results)
    cost = sum(r["result"].cost_usd for r in results)
    tin = sum(r["result"].input_tokens for r in results)
    tout = sum(r["result"].output_tokens for r in results)

    lines = [
        "# Character demo — live agent analysis",
        "",
        f"**Run {run_date}** · model `{info.model_name}` · mode `{info.mode.value}`",
        "",
        f"{len(results)} entries · **{calls} model calls** · "
        f"{tin:,} input / {tout:,} output tokens · **${cost:.4f}**",
        "",
        "These are the demo's proof-point entries. They carry no hand-written analysis:",
        "everything below was produced by the agents and then frozen into",
        "`data/characters/*.json` so the hosted app shows it without re-spending.",
        "",
        "| Character | Entry | Calls | Cost | Observations | Evidence | Questions | Safety |",
        "|---|---|--:|--:|--:|--:|--:|--:|",
    ]
    for r in results:
        h = harvested.get(r["key"], {})
        lines.append(
            f"| {r['name']} | `{r['key']}` | {r['result'].model_calls} | "
            f"${r['result'].cost_usd:.5f} | {len(h.get('observations', []))} | "
            f"{len(h.get('evidence', []))} | {len(h.get('interrogations', []))} | "
            f"{len(h.get('safety', [])) or '—'} |"
        )
    lines += ["", f"**Total ${cost:.4f}** across {calls} calls.", ""]

    errs = [(r["name"], r["key"], r["result"].errors) for r in results if r["result"].errors]
    if errs:
        lines += ["## Errors", ""]
        lines += [f"- **{n}** `{k}`: {e}" for n, k, e in errs] + [""]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes-spend-credits", action="store_true",
                    help="Required. Live model calls cost real money.")
    ap.add_argument("--only", nargs="*", default=None,
                    help="Entry keys to run, instead of all of them.")
    ap.add_argument("--smoke", action="store_true",
                    help="Exercise the whole path in demo mode, free, writing nothing "
                         "back. Proves the plumbing before any paid run — a crash after "
                         "ten billed calls is a waste of ten billed calls.")
    args = ap.parse_args()

    pairs = flagged()
    if args.only:
        pairs = [(c, e) for c, e in pairs if e["key"] in args.only]
        if not pairs:
            print(f"No flagged entry matches {args.only}", file=sys.stderr)
            return 1

    n = estimate(pairs)
    print(f"{len(pairs)} entries, about {n} model calls "
          f"(~${n * 0.00052:.3f} at measured rates).\n")

    if not args.yes_spend_credits and not args.smoke:
        print("  Estimate only. Nothing has been spent.")
        print("  Re-run with --yes-spend-credits to actually call the model,")
        print("  or --smoke to exercise the whole path for free first.")
        return 0

    if args.smoke:
        model, info = build(Mode.DEMO)
        db = Path(tempfile.mkdtemp()) / "smoke.db"
        store = Store(db)
        accounts = seed(store, reset=True)
        print(f"SMOKE ({info.mode.value}, nothing billed, nothing written back)\n")
        results = asyncio.run(analyse(store, accounts, pairs, model, info))
        harvested = harvest(db, results)
        rows = sum(len(v["observations"]) + len(v["evidence"])
                   + len(v["interrogations"]) for v in harvested.values())
        print(f"\nHarvest read {rows} generated row(s) back out of the database.")
        print("Write-back deliberately skipped: simulated output must never be frozen "
              "into the demo as real analysis.")
        return 0

    model, info = build()
    if info.mode is not Mode.LIVE:
        print(f"Provider is in {info.mode.value} mode, not live. "
              f"Simulated output cannot be frozen into the demo as real analysis.",
              file=sys.stderr)
        return 1

    db = Path(tempfile.mkdtemp()) / "characters.db"
    store = Store(db)
    accounts = seed(store, reset=True)
    print(f"Seeded {len(accounts)} accounts into {db}\n")

    results = asyncio.run(analyse(store, accounts, pairs, model, info))
    harvested = harvest(db, results)
    run_date = date.today().isoformat()
    touched = write_back(harvested, info, run_date)
    report(results, harvested, info, run_date)

    cost = sum(r["result"].cost_usd for r in results)
    calls = sum(r["result"].model_calls for r in results)
    print(f"\n{calls} calls, ${cost:.4f}. Frozen into {touched} character file(s).")
    print(f"Report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
