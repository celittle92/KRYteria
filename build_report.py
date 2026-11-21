#!/usr/bin/env python3
"""Assemble ``report.html`` as a single self-contained file.

The assignment is explicit: both HTML deliverables must open by double-clicking, on any
computer, with every screenshot showing. So images are base64-inlined rather than linked
— a relative path works on the machine that made it and nowhere else, and "the images
were missing" is not a thing worth losing points to.

Run from the project root:

    .venv/bin/python build_report.py

The prose lives in ``report_body.html`` beside this script. Keeping it out of a Python
string means it can be edited as HTML, by a person, without fighting escaping.
"""

from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BODY = HERE / "report_body.html"
SLIDES_BODY = HERE / "slides_body.html"
SHOTS = HERE / "output" / "screenshots"
OUT = HERE / "report.html"
SLIDES_OUT = HERE / "slides.html"

#: Every image the body may reference, by the token used in the HTML.
IMAGES = {
    "FRONT_DOOR": "front-door.png",
    "PATTERNS_DARK": "patterns-dark.png",
    "PATTERNS_WARM": "patterns-warm.png",
    "PROFILES_DARK": "profiles-dark.png",
    "PROGRESS_DARK": "progress-dark.png",
    "JOURNAL_DARK": "journal-dark.png",
    "TRACE_DARK": "trace-dark.jpg",
}


def data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def build(body_path, out_path, label: str) -> int:
    """Inline every referenced image and write a self-contained file."""
    if not body_path.is_file():
        print(f"Missing {body_path}", file=sys.stderr)
        return 1
    html = body_path.read_text(encoding="utf-8")

    # Template-only blocks. The body files are openable HTML, which is useful while
    # editing and is also a trap: opening report_body.html shows {{PLACEHOLDER}} text
    # where the screenshots go, and it looks like the images are broken. It has caught
    # the author twice. The template therefore carries a loud banner saying "open
    # report.html instead", and that banner is stripped here so it never ships.
    stripped = len(re.findall(r"<!-- BUILD:STRIP-START", html))
    html = re.sub(r"<!-- BUILD:STRIP-START.*?BUILD:STRIP-END -->\n?", "", html,
                  flags=re.DOTALL)

    missing, used = [], []
    for token, filename in IMAGES.items():
        placeholder = "{{" + token + "}}"
        if placeholder not in html:
            continue              # registered but not referenced; reported at the end
        used.append(token)
        path = SHOTS / filename
        if not path.is_file():
            missing.append(filename)
            continue
        html = html.replace(placeholder, data_uri(path))

    if missing:
        print(f"Missing screenshots: {', '.join(missing)}", file=sys.stderr)
        return 1

    left = re.findall(r"\{\{[A-Z_]+\}\}", html)
    if left:
        print(f"Unresolved placeholders: {sorted(set(left))}", file=sys.stderr)
        return 1

    out_path.write_text(html, encoding="utf-8")
    kb = out_path.stat().st_size / 1024
    # Report what was actually embedded, not how many are on offer. These differed once
    # — two screenshots were generated and registered but never referenced — and the
    # count said six while the report showed four.
    print(f"Wrote {out_path.name} — {kb:,.0f} KB, self-contained "
          f"({len(used)} of {len(IMAGES)} registered images inlined"
          f"{f', {stripped} template-only block(s) stripped' if stripped else ''}).")
    unused = [t for t in IMAGES if t not in used]
    if unused:
        print(f"  NOTE: registered but unused: {', '.join(sorted(unused))}")
    # Count TODOs in the SOURCE, not the built file. Once the images are inlined the
    # output carries megabytes of base64, and "TODO" turns up in it by chance — the
    # warning said three when the report had two.
    source = body_path.read_text(encoding="utf-8")
    if "TODO" in source:
        n = source.count("TODO")
        print(f"  NOTE: {n} TODO marker(s) still in the {label}. "
              "They are styled to be impossible to miss on the page.")
    return 0


def main() -> int:
    rc = build(BODY, OUT, "report")
    if rc:
        return rc
    if SLIDES_BODY.is_file():
        rc = build(SLIDES_BODY, SLIDES_OUT, "deck")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
