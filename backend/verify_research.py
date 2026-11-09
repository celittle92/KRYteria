"""Verify knowledge-base entries, one at a time, by hand.

A research note is invisible to the agents until somebody opens the source and confirms
the finding is characterised fairly. This is the tool for doing that, and it refuses to
record a verification without the URL of whatever was actually opened.

    .venv/bin/python -m backend.verify_research list
    .venv/bin/python -m backend.verify_research show gottman-bids
    .venv/bin/python -m backend.verify_research ok gottman-bids --url https://... --by christine
    .venv/bin/python -m backend.verify_research load

Verification is not a formality. Taking the entry's word for its own citation would put
us back where we started: a plausible reference nobody checked.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from .store import Store

PACK = Path(__file__).resolve().parent.parent / "data" / "research"


def _wrap(text: str, indent: str = "    ") -> str:
    return textwrap.fill(text, width=92, initial_indent=indent, subsequent_indent=indent)


def cmd_load(store: Store, args) -> None:
    added = refreshed = kept = 0
    for path in sorted(PACK.glob("*.json")):
        r = store.load_research_pack(path)
        print(f"{path.name}: {r['added']} new, {r['refreshed']} refreshed, "
              f"{r['kept_verified']} already verified and left alone")
        added += r["added"]
        refreshed += r["refreshed"]
        kept += r["kept_verified"]
    if kept:
        print(f"\n{kept} verified entries were NOT overwritten. Re-verify deliberately "
              "if their wording changed in the file.")
    print(f"\n{len(store.citable_refs())} entries are citable; the rest are pending and "
          "invisible to the agents.")


def cmd_list(store: Store, args) -> None:
    notes = store.list_research_notes(include_pending=True, include_safety_adjacent=True)
    if not notes:
        print("Knowledge base is empty. Run `load` first.")
        return
    pending = [n for n in notes if not n["verified_at"]]
    done = [n for n in notes if n["verified_at"]]
    print(f"{len(done)} verified · {len(pending)} pending\n")
    partial = 0
    for n in notes:
        mark = "✓" if n["verified_at"] else "·"
        flags = "  [safety-adjacent]" if n["safety_adjacent"] else ""
        conf = n.get("citation_confidence") or ""
        if conf and not conf.startswith("bibliography_confirmed"):
            flags += "  ⚠ citation unsettled"
            partial += 1
        print(f" {mark} {n['ref']:<36} {n['area']}{flags}")
    if partial:
        print(f"\n⚠ {partial} entries have a citation detail that could not be "
              "confirmed. `show <ref>` says which part.")
    if pending:
        print(f"\nThe agents can currently cite {len(done)} of {len(notes)} entries.")
        print("Check a source, then:  ok <ref> --url <what you opened> --by <your name>")


def cmd_show(store: Store, args) -> None:
    notes = store.list_research_notes(include_pending=True, include_safety_adjacent=True)
    note = next((n for n in notes if n["ref"] == args.ref), None)
    if note is None:
        raise SystemExit(f"No entry {args.ref!r}. Try `list`.")

    print(f"\n{note['ref']}   [{note['area']}]")
    print("=" * 92)
    if note["concept"]:
        print(f"\nCONCEPT\n{_wrap(note['concept'])}")
    print(f"\nFINDING AS DRAFTED\n{_wrap(note['finding'])}")
    print(f"\nATTRIBUTION\n{_wrap(note['attribution'] or '(none)')}")
    print(f"\nCITATION TO CHECK\n{_wrap(note['citation'])}")
    confidence = note.get("citation_confidence")
    if confidence:
        flag = "" if confidence.startswith("bibliography_confirmed") else "  ⚠"
        print(f"\nBIBLIOGRAPHY{flag}\n{_wrap(confidence)}")
    if note.get("citation_checked_against"):
        print(_wrap(note["citation_checked_against"]))
    print(f"\nCAVEAT\n{_wrap(note['caveat'])}")
    if note["do_not"]:
        print("\nDO NOT")
        for d in note["do_not"]:
            print(_wrap(f"- {d}"))
    if note["indicator_hints"]:
        print("\nINDICATOR HINTS")
        for h in note["indicator_hints"]:
            print(_wrap(f"- {h}"))
    print("\n" + "-" * 92)
    if note["verified_at"]:
        print(f"VERIFIED {note['verified_at']} by {note['verified_by']}")
        print(f"SOURCE   {note['source_url']}")
    else:
        print("PENDING — invisible to the agents.\n")
        print("What to check before promoting it:")
        print("  1. The work exists and the attribution is right.")
        print("  2. The finding as drafted is a fair characterisation, not an")
        print("     overstatement of what the research actually showed.")
        print("  3. The caveat is true and sufficient.")
        print(f"\n  ok {note['ref']} --url <what you opened> --by <your name>")


def cmd_ok(store: Store, args) -> None:
    store.verify_research_note(args.ref, source_url=args.url, verified_by=args.by)
    citable = store.citable_refs()
    print(f"✓ {args.ref} verified by {args.by}")
    print(f"  source: {args.url}")
    print(f"\n{len(citable)} entries are now citable.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify KRYteria's research knowledge base by hand.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load", help="load data/research/*.json (everything arrives pending)")
    sub.add_parser("list", help="show every entry and its verification state")
    p_show = sub.add_parser("show", help="show one entry in full, with what to check")
    p_show.add_argument("ref")
    p_ok = sub.add_parser("ok", help="mark an entry verified")
    p_ok.add_argument("ref")
    p_ok.add_argument("--url", required=True, help="what you actually opened")
    p_ok.add_argument("--by", required=True, help="who checked it")

    args = parser.parse_args()
    store = Store()
    {"load": cmd_load, "list": cmd_list, "show": cmd_show, "ok": cmd_ok}[args.cmd](
        store, args
    )


if __name__ == "__main__":  # pragma: no cover
    main()
