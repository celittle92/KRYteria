"""Verify knowledge-base entries, one at a time, by hand.

A research note is invisible to the agents until somebody opens the source and confirms
the finding is characterized fairly. This is the tool for doing that, and it refuses to
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
import datetime as _dt
import json
import textwrap
from pathlib import Path

from .store import Store


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

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
        print("  2. The finding as drafted is a fair characterization, not an")
        print("     overstatement of what the research actually showed.")
        print("  3. The caveat is true and sufficient.")
        print(f"\n  ok {note['ref']} --url <what you opened> --by <your name>")


def record_in_pack(ref: str, *, source_url: str, verified_by: str,
                   verified_at: str) -> Path | None:
    """Write the verification into the pack file, not only into the database.

    **Why this exists.** Until 2026-11-11 ``ok`` wrote to the database alone, and
    ``CLAUDE.md`` instructs you to delete that database whenever the schema changes.
    Adding the ``entry_themes`` table did exactly that, and eighteen verifications — the
    only part of this knowledge base a human actually signed — vanished with it. The
    curated pack is the committed artifact; the database is disposable. Verification
    belongs in the artifact.

    ``load_research_pack`` already honors ``verification_status: verified`` and applies
    the same source gate on the way in, so nothing is weakened by storing it here: a pack
    still cannot mark its own work verified against a source KRYteria would not cite.
    """
    for path in sorted(PACK.glob("*.json")):
        blob = json.loads(path.read_text(encoding="utf-8"))
        for note in blob.get("notes", []):
            if note.get("id") != ref:
                continue
            note["verification_status"] = "verified"
            note["verified_at"] = verified_at
            note["verified_by"] = verified_by
            note["source_url"] = source_url
            path.write_text(json.dumps(blob, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
            return path
    return None


def cmd_ok(store: Store, args) -> None:
    store.verify_research_note(args.ref, source_url=args.url, verified_by=args.by)
    row = next((n for n in store.list_research_notes(
        include_pending=True, include_safety_adjacent=True) if n["ref"] == args.ref), None)
    written = record_in_pack(args.ref, source_url=args.url, verified_by=args.by,
                             verified_at=row["verified_at"] if row else _now_iso())
    citable = store.citable_refs()
    print(f"✓ {args.ref} verified by {args.by}")
    if written:
        print(f"  recorded in {written.name} — survives a database rebuild")
    else:
        print("  WARNING: not found in any pack file; this verification lives only in "
              "the database and will be lost on the next schema change.")
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
