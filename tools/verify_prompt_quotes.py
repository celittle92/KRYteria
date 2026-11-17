"""Check every word attributed to Christine in the catch-up against the transcript.

The prompt record's one rule is that her words are verbatim. This checks that mechanically
rather than trusting that they were typed carefully: each blockquote in the new section is
split on the elision marker and every piece must appear in the extracted transcript text.

Normalises curly quotes, dashes and whitespace, because the record is Markdown and the
transcript is raw, not because a wording difference would be acceptable.
"""

import re
import sys
import unicodedata
from pathlib import Path

RECORD = Path(sys.argv[1])
SOURCE = Path(sys.argv[2])
MARKER = sys.argv[3] if len(sys.argv) > 3 else "## Catch-up"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("—", "-"), ("–", "-"), ("…", "...")):
        s = s.replace(a, b)
    s = s.replace("**", "").replace("*", "")
    return " ".join(s.split()).lower()


def blocks(lines):
    """Consecutive '> ' lines are one quoted block; a bare '>' is a paragraph break."""
    out, cur = [], []
    for line in lines:
        if line.startswith(">"):
            body = line[1:].strip()
            if body:
                cur.append(body)
            else:
                cur.append("")
        else:
            if cur:
                out.append(cur)
                cur = []
    if cur:
        out.append(cur)
    return out


def main() -> int:
    text = RECORD.read_text(encoding="utf-8")
    at = text.index(MARKER)
    lines = text[at:].split("\n")
    hay = norm(SOURCE.read_text(encoding="utf-8"))

    checked = missing = 0
    for block in blocks(lines):
        joined = " ".join(x for x in block if x)
        for piece in joined.split("[...]"):
            for piece2 in piece.split("[…]"):
                p = norm(piece2)
                if len(p) < 25:          # too short to be a meaningful check
                    continue
                checked += 1
                if p not in hay:
                    missing += 1
                    print("NOT FOUND VERBATIM:")
                    print("   " + p[:300])
    print(str(checked) + " quoted fragments checked, " + str(missing) + " not found")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
