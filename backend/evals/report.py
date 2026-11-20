"""Turn a run into the two artifacts: machine-readable JSON and a readable Markdown page.

The Markdown is what gets screenshotted into the report, so the mode banner is the first
thing on it and is deliberately hard to crop out of a screenshot accidentally. A demo-mode
page that looked like a real result would be the single most misleading thing this
project could produce.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import checks as checks_mod
from .runner import totals

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_DIR / "output"

#: Demo runs go here, NOT into output/. The submission checker treats a file in output/
#: as a required artifact being present, and a demo-mode page landing on
#: output/safety_results.json would turn that check green over a run that graded nothing.
#: A banner on the page is not enough when the thing reading it is a script.
DEMO_DIR = OUTPUT_DIR / "demo_runs"


def _target(report: dict) -> Path:
    """Where this run is allowed to write. Only a live run earns the real names."""
    return OUTPUT_DIR if not report["simulated"] else DEMO_DIR

_MARK = {
    checks_mod.PASS: "PASS",
    checks_mod.FAIL: "**FAIL**",
    checks_mod.REVIEW: "review",
    checks_mod.NA: "n/a",
}


def _banner(report: dict) -> list[str]:
    if report["simulated"]:
        return [
            "> ## ⚠ DEMO MODE — THIS IS NOT EVIDENCE",
            ">",
            f"> Run in `{report['mode']}` mode against `{report['model']}`, which makes "
            "no model call.",
            "> It proves the harness and the case definitions execute. It grades "
            "**nothing** about",
            "> how the real agents behave, and no figure on this page belongs in a "
            "report or a slide.",
            ">",
            "> Re-run with `--mode live --yes-spend-credits` for a result that means "
            "something.",
            "",
        ]
    return [
        f"> **Live run** against `{report['model']}` on {report['ran_at']}. "
        f"Real model calls; these results are evidence.",
        "",
    ]


def _case_block(case: Any) -> list[str]:
    lines = [f"### `{case.case_id}` — {case.title}", ""]
    lines += [f"> {case.user_input}", ""]
    if case.error:
        lines += [f"**The case did not run:** `{case.error}`", ""]
        return lines

    lines += ["| | Check | What it is for | Result |", "|---|---|---|---|"]
    for r in case.rows:
        spec = {k: v for k, v in r["spec"].items() if k not in ("check", "says")}
        detail = r["detail"].replace("|", "\\|")
        arg = f"`{json.dumps(spec)}`" if spec else ""
        lines.append(
            f"| {_MARK[r['outcome']]} | `{r['check']}` {arg} | "
            f"{(r['says'] or '').replace('|', chr(92) + '|')} | {detail} |"
        )
    lines.append("")

    t = case.transcript
    if t and t.prose:
        lines += ["<details><summary>What the agents produced</summary>", ""]
        shown = t.prose[:2000]
        lines += ["```", shown, "```"]
        if len(t.prose) > len(shown):
            lines += ["", f"*Truncated at 2,000 of {len(t.prose):,} characters for "
                          "readability. The full text is in the `.json` beside this "
                          "file, under `produced.prose` — never adjudicate a failure "
                          "from this excerpt alone.*"]
        lines += ["", "</details>", ""]
    return lines


def to_markdown(report: dict, *, title: str) -> str:
    agg = totals(report)
    lines = [f"# {title}", ""]
    lines += _banner(report)
    lines += [
        f"Pack `{report['pack']}` v{report['pack_version']} · "
        f"{agg['total_cases']} cases · {report['duration_s']}s",
        "",
        "| Cases | | Checks | |",
        "|---|---|---|---|",
        f"| passed | {agg['cases'][checks_mod.PASS]} | passed | "
        f"{agg['checks'][checks_mod.PASS]} |",
        f"| **failed** | **{agg['cases'][checks_mod.FAIL]}** | **failed** | "
        f"**{agg['checks'][checks_mod.FAIL]}** |",
        f"| need review | {agg['cases'][checks_mod.REVIEW]} | need review | "
        f"{agg['checks'][checks_mod.REVIEW]} |",
        f"| errored | {agg['cases']['error']} | not applicable | "
        f"{agg['checks'][checks_mod.NA]} |",
        "",
        "A case counts as passed only when every one of its checks passed. A case with "
        "any check needing human review is reported as needing review, never as a pass.",
        "",
    ]

    if report.get("universal_must_not"):
        lines += ["## What no response may ever do", ""]
        lines += [f"- {x}" for x in report["universal_must_not"]]
        lines += [""]

    lines += ["## Cases", ""]
    for case in report["cases"]:
        lines += _case_block(case)

    pending = [(c.case_id, r["says"]) for c in report["cases"] for r in c.rows
               if r["outcome"] == checks_mod.REVIEW]
    if pending:
        lines += ["## Still needs a person", "",
                  "No honest predicate exists for these, so the harness does not "
                  "pretend. Read the case and tick it off.", ""]
        for cid, says in pending:
            lines.append(f"- [ ] `{cid}` — {says}")
        lines.append("")
    return "\n".join(lines)


def _serialisable(report: dict) -> dict:
    out = dict(report)
    out["cases"] = [
        {
            "id": c.case_id, "pack": c.pack, "title": c.title,
            "user_input": c.user_input, "verdict": c.verdict,
            "counts": c.counts, "error": c.error,
            "checks": [
                {k: v for k, v in r.items() if k != "spec"} | {"spec": r["spec"]}
                for r in c.rows
            ],
            "produced": None if not c.transcript else {
                "model_calls": c.transcript.model_calls,
                "input_tokens": c.transcript.input_tokens,
                "output_tokens": c.transcript.output_tokens,
                "latency_ms": c.transcript.latency_ms,
                "simulated": c.transcript.simulated,
                # Counts for scanning, and the rows themselves for adjudicating. The
                # count alone was all this file stored, so when the first live
                # reasoning run failed `observation_of_kind` on two cases there was no
                # way to tell whether the agent had missed the observation or the check
                # had missed the agent — without paying for the run again. Same lesson
                # as the prose truncation below, learned a second time.
                "observation_count": len(c.transcript.observations),
                "observations": c.transcript.observations,
                "mappings_count": len(c.transcript.mappings),
                "mappings": c.transcript.mappings,
                "patterns": len(c.transcript.patterns),
                "proposals": len(c.transcript.proposals),
                "safety_events": c.transcript.safety_events,
                "halted": c.transcript.halted,
                "errors": c.transcript.errors,
                # The FULL text, untruncated. The Markdown cuts prose at 2,000
                # characters for readability, and on the first live safety run that
                # hid the sentence which tripped a `prose_lacks` check — leaving a
                # real failure unadjudicable without paying for the run again.
                # Evidence that cost money must be complete in the machine-readable
                # artifact, whatever the page does for the eye.
                "prose": c.transcript.prose,
                "attributed": c.transcript.attributed,
            },
        }
        for c in report["cases"]
    ]
    out["totals"] = totals(report)
    return out


def write(report: dict, *, stem: str, title: str) -> tuple[Path, Path]:
    target = _target(report)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / f"{stem}.json"
    md_path = target / f"{stem}.md"
    json_path.write_text(json.dumps(_serialisable(report), indent=2, ensure_ascii=False)
                         + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(report, title=title) + "\n", encoding="utf-8")
    return json_path, md_path


# ------------------------------------------------------------------ the A/B

def ab_to_markdown(report: dict) -> str:
    lines = ["# KRYteria vs. a general-purpose chatbot", ""]
    if report["simulated"]:
        lines += [
            "> ## ⚠ DEMO MODE — THIS IS NOT A COMPARISON",
            ">",
            "> No model was called, so the 'baseline' below is a placeholder string and "
            "KRYteria's",
            "> side is scripted. Nothing here may be quoted. Re-run with `--mode live "
            "--yes-spend-credits`.",
            "",
        ]
    else:
        lines += [f"> **Live run** against `{report['model']}` on {report['ran_at']}. "
                  f"Both systems on the same model, same entries.", ""]

    lines += [
        report["dimensions_note"], "",
        f"Baseline prompt: `backend/prompts/{report['baseline_prompt']}` — written to be "
        "a *fair* generic assistant, not a strawman.", "",
    ]

    won = tied = lost = 0
    for s in report["scenarios"]:
        k = s["systems"]["kryteria"]["passed"]
        b = s["systems"]["generic_chatbot"]["passed"]
        won += k > b
        tied += k == b
        lost += k < b
    lines += [
        "## Summary", "",
        "| | Scenarios |", "|---|---|",
        f"| KRYteria scored higher | {won} |",
        f"| Tied | {tied} |",
        f"| Baseline scored higher | {lost} |",
        "", "---", "",
    ]

    for s in report["scenarios"]:
        kry, base = s["systems"]["kryteria"], s["systems"]["generic_chatbot"]
        lines += [f"## {s['id']} — {s['title']}", ""]
        if s.get("why_this_one"):
            lines += [f"*{s['why_this_one']}*", ""]
        lines += [f"> {s['user_input']}", ""]
        lines += [
            f"**KRYteria {kry['passed']}/{len(s['dimensions'])} · "
            f"baseline {base['passed']}/{len(s['dimensions'])}**", "",
            "| Dimension | KRYteria | Chatbot |", "|---|---|---|",
        ]
        for i, d in enumerate(s["dimensions"]):
            lines.append(
                f"| {d['says'].replace('|', chr(92) + '|')} "
                f"| {_MARK[kry['rows'][i]['outcome']]} "
                f"| {_MARK[base['rows'][i]['outcome']]} |"
            )
        lines += [""]

        lines += ["**What each system produced at all** — capability, reported beside "
                  "the score and never inside it:", "",
                  "| | KRYteria | Chatbot |", "|---|---|---|"]
        for key in kry["capability"]:
            lines.append(f"| {key.replace('_', ' ')} | {kry['capability'][key]} "
                         f"| {base['capability'][key]} |")
        lines += [""]

        lines += ["<details><summary>The chatbot's reply</summary>", "",
                  "```", (base["prose"] or "(nothing)")[:2500], "```", "",
                  "</details>", "",
                  "<details><summary>What KRYteria produced</summary>", "",
                  "```", (kry["prose"] or "(nothing)")[:2500], "```", "",
                  "</details>", "", "---", ""]

    manual = [(s["id"], d["says"]) for s in report["scenarios"]
              for d in s["dimensions"] if d["check"] == "manual"]
    if manual:
        lines += ["## Read these yourself", "",
                  "Quality is not a substring match. Both replies are above; these are "
                  "the questions worth answering by eye.", ""]
        lines += [f"- [ ] `{sid}` — {says}" for sid, says in manual]
        lines += [""]
    return "\n".join(lines)


def write_ab(report: dict) -> tuple[Path, Path]:
    target = _target(report)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "ab_comparison.json"
    md_path = target / "ab_comparison.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    md_path.write_text(ab_to_markdown(report) + "\n", encoding="utf-8")
    return json_path, md_path
