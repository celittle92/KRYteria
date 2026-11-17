#!/usr/bin/env python3
"""Every number this project states in prose, checked against the thing it describes.

WHY THIS EXISTS. KRYteria states the same quantity in up to six places — `README.md`,
`report_body.html`, `slides_body.html`, `output/harness.md`, `output/token_report.md`,
`docs/`. Every one of them was written by hand, and over three weeks they drifted: the
README claimed 476 checks and then 976 against an actual 1,340; the report said 33 tables
against a schema with 34, "seven runtime prompts" against eight files, "nine entries" in a
directory holding ten, and "fires 24 times" against 22. None of those were lies when
written. They were true once.

An audit caught them. An audit is a person reading carefully, once, and it does not
survive the next edit — so the rule here is the same one the tokenomics section already
follows: **derive the number from the source and compare, rather than trusting that it
was typed correctly.**

    python3 tools/check_consistency.py          # numbers only, fast, no model calls
    python3 tools/check_consistency.py --tests  # also runs all five suites for the real counts

Exit code 1 if anything disagrees, so it can gate a commit.

WHAT IT DELIBERATELY DOES NOT DO. It cannot tell you a sentence has gone stale, only that
a number has. "The front end is not started" was wrong for a week and contains no digits.
Prose still needs a person.
"""

from __future__ import annotations

import argparse
import glob
import os
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

#: Files whose numbers are read by somebody other than us.
DELIVERABLES = [
    "README.md", "report_body.html", "slides_body.html",
    "output/harness.md", "output/token_report.md", "docs/privacy.md",
]


# --------------------------------------------------------------------------- truth

def truth() -> dict[str, object]:
    """Count the things, rather than remembering them."""
    g = lambda p: sorted(glob.glob(str(HERE / p)))
    read = lambda p: (HERE / p).read_text(encoding="utf-8")
    t: dict[str, object] = {}

    t["tables"] = len(re.findall(r"^CREATE TABLE", read("backend/schema.sql"), re.M))
    t["prompts"] = len(g("backend/prompts/*.md"))
    t["agents"] = len([f for f in g("backend/agents/*.py")
                       if Path(f).name not in ("__init__.py", "base.py")])
    t["test_functions"] = sum(len(re.findall(r"^def test_", Path(f).read_text(encoding="utf-8"), re.M))
                              for f in g("tests/test_*.py"))

    chars = g("data/characters/*.json")
    t["characters"] = len(chars)
    for key in ("profiles", "criteria", "entries", "assessments"):
        t["demo_" + key] = sum(len(json.loads(Path(f).read_text(encoding="utf-8")).get(key, []))
                               for f in chars)
    t["definition_interrogations"] = sum(
        1 for f in chars
        for e in json.loads(Path(f).read_text(encoding="utf-8")).get("entries", [])
        for i in (e.get("generated") or {}).get("interrogations", [])
        if i.get("gap_kind") == "definition")

    rows = lambda p: (lambda d: d.get("resources", d))(json.loads(read(p)))
    t["resources_us"] = len(rows("data/resources_us.json"))
    t["resources_intl"] = len(rows("data/resources_international.json"))

    notes = json.loads(read("data/research/behavioral_indicators.json"))
    notes = notes.get("notes", notes.get("research_notes", notes))
    t["research_total"] = len(notes)
    t["research_verified"] = sum(1 for n in notes if n.get("verified_at"))

    runs = json.loads(read("output/usage_log.json"))["runs"]
    measured = [r for r in runs if r["calls"] is not None]
    t["runs_total"] = len(runs)
    t["runs_measured"] = len(measured)
    t["calls"] = sum(r["calls"] for r in measured)
    t["tokens_in"] = sum(r["input_tokens"] for r in measured)
    t["tokens_out"] = sum(r["output_tokens"] for r in measured)
    t["cost"] = round(sum(r.get("cost_usd") or 0 for r in measured), 5)
    return t


def run_suites() -> int:
    """The real check count, by running them. Free: no API key, no network."""
    total = 0
    for name, interp in (("test_offline", "python3"),
                         ("test_contracts", ".venv/bin/python"),
                         ("test_wiring", ".venv/bin/python"),
                         ("test_api", ".venv/bin/python"),
                         ("test_evals", ".venv/bin/python")):
        # Inherit the environment and add to it. Replacing it wholesale drops TMPDIR,
        # and Python's tempfile then falls back through /tmp to the CURRENT DIRECTORY —
        # which littered 125 `tmp*/` directories into the repo root the first time this
        # ran. Harmless until somebody types `git add -A`, which is how this project
        # commits.
        env = {**os.environ, "PYDANTIC_AI_NO_BANNER": "1"}
        out = subprocess.run([interp, f"tests/{name}.py"], cwd=HERE,
                             capture_output=True, text=True, env=env)
        m = re.search(r"(\d+) passed, (\d+) failed", out.stdout)
        if not m:
            print(f"  !! could not read a result from {name}")
            continue
        passed, failed = int(m.group(1)), int(m.group(2))
        if failed:
            print(f"  !! {name}: {failed} FAILED")
        total += passed
    return total


# --------------------------------------------------------------------------- claims

def claims(t: dict[str, object]) -> list[tuple[str, object, str]]:
    """(label, expected, regex). The regex captures the number as it appears in prose."""
    n = lambda x: f"{x:,}"
    return [
        ("schema tables",            t["tables"],      r"(\d+) tables"),
        ("demo characters",          t["characters"],  r"(nine|\d+)[- ]character demo"),
        ("demo profiles",            t["demo_profiles"], r"(\d+) profiles"),
        ("demo criteria",            t["demo_criteria"], r"(\d+) criteria,"),
        ("demo entries",             t["demo_entries"],  r"(\d+) entries,"),
        # Anchored on the words around them. A loose `\d+ of (\d+)` also matches
        # "11 of 12 runs", "33 of 128 checks" and "3 of 13 cases", and a checker that
        # cries wolf gets ignored, which is worse than not having one.
        ("research verified",        t["research_verified"],
         r"(\d+) of \d+ (?:are |findings )?verified"),
        ("research total",           t["research_total"],
         r"\d+ of (\d+) (?:are |findings )?verified"),
        ("mapping audit fires",      t["definition_interrogations"],
         r"fires (?:<strong>|\*\*)?(\d+) times"),
        ("live calls",               t["calls"],
         r"(\d{3}) (?:measured )?(?:live )?(?:model )?calls"),
        ("input tokens",             n(t["tokens_in"]),
         r"([\d,]{7,}) (?:measured )?input"),
        ("output tokens",            n(t["tokens_out"]), r"([\d,]{7,}) output"),
        ("resources, intl",          t["resources_intl"],
         r"(ten|nine|\d+) entries we can stand"),
        ("runs, measured",           t["runs_measured"], r"(\d+) measured runs"),
        ("runs, total",              t["runs_total"],    r"(\d+) live\s+runs"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", action="store_true",
                    help="also run the five suites for the real check count")
    args = ap.parse_args()

    t = truth()
    print("Ground truth, counted from source:")
    for k, v in t.items():
        print(f"  {k:28} {v}")

    problems = 0

    if args.tests:
        print("\nRunning the suites (free, no API key)…")
        checks = run_suites()
        print(f"  {'checks passing':28} {checks}")
        print(f"  {'test functions':28} {t['test_functions']}")
        for path in DELIVERABLES + ["output/report_notes.md", "CLAUDE.md"]:
            f = HERE / path
            if not f.is_file():
                continue
            text = f.read_text(encoding="utf-8")
            # Only four-figure counts are the project-wide total. Three-figure ones are
            # legitimate per-suite breakdowns (515 offline, 273 API…) or the 128 eval
            # checks, which are a different population; and `report_notes.md` quotes the
            # old wrong totals on purpose, inside the account of how they were wrong.
            for m in re.finditer(r"([\d,]{5,6}) (?:automated )?checks", text):
                if int(m.group(1).replace(",", "")) != checks:
                    print(f"  MISMATCH {path}: says {m.group(1)} checks, actual {checks:,}")
                    problems += 1
            for m in re.finditer(r"(\d+) test functions", text):
                if int(m.group(1)) != t["test_functions"]:
                    print(f"  MISMATCH {path}: says {m.group(1)} test functions, "
                          f"actual {t['test_functions']}")
                    problems += 1

    print("\nClaims in the deliverables:")
    seen: set[str] = set()
    words = {"nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "seven": 7, "eight": 8}
    for path in DELIVERABLES:
        f = HERE / path
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        for label, expected, pattern in claims(t):
            for m in re.finditer(pattern, text, re.I):
                got = m.group(1)
                norm = words.get(got.lower(), got)
                if str(norm).replace(",", "") != str(expected).replace(",", ""):
                    ctx = text[max(0, m.start() - 60):m.end() + 40].replace("\n", " ")
                    print(f"  MISMATCH {path}: {label} says {got!r}, source says {expected}")
                    print(f"           …{ctx.strip()}…")
                    problems += 1
                seen.add(label)

    never = [c[0] for c in claims(t) if c[0] not in seen]
    if never:
        print("\n  Claims whose pattern matched nowhere (check the regex, not the docs):")
        for label in never:
            print(f"    - {label}")

    # The spend table has to add up to its own Total and to the log.
    md = (HERE / "output/token_report.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| \d\d-\d\d \| .+? \| (\d+|—) \| ([\d,]+|—) \| ([\d,]+|—) \| (\$[\d.]+|—) \|",
                      md, re.M)
    num = lambda x: 0 if x == "—" else int(x.replace(",", ""))
    summed = (sum(num(r[0]) for r in rows), sum(num(r[1]) for r in rows),
              sum(num(r[2]) for r in rows),
              round(sum(float(r[3][1:]) for r in rows if r[3] != "—"), 5))
    if summed != (t["calls"], t["tokens_in"], t["tokens_out"], t["cost"]):
        print(f"  MISMATCH token_report.md rows sum to {summed}, log says "
              f"{(t['calls'], t['tokens_in'], t['tokens_out'], t['cost'])}")
        problems += 1
    else:
        print("  OK  token_report.md rows sum to the usage log")

    print(f"\n{problems} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
