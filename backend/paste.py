"""Turn a pasted list of standards into criteria rows — deterministically, no model call.

Somebody who already knows what they want has usually already written it down: in a
note, a document, a thread with a friend. Making them retype it one field at a time is
the single most reliable way to lose them before the product has done anything for them.

Two rules govern everything in this module.

**It never writes the user's standards for them.** A line with no "what meeting it looks
like" produces a criterion with that field empty, not one with a plausible sentence the
app invented. Suggesting observable indicators is the Criteria agent's job, and it is a
job the user opts into and confirms — not something that happens silently to twenty rows
because she pasted a list.

**It never silently changes what she wrote.** A line too long for the column is reported
and skipped, never truncated. A line this parser cannot split is kept whole as the value
rather than guessed at. Everything it did is shown back for review before anything is
written, which is why ``parse_paste`` is pure and the route that uses it writes nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: The schema's limits. A line that would not fit is refused, not cut down.
MAX_VALUE = 200
MAX_BEHAVIOR = 1000

#: A paste, not a document. Twenty-odd standards is a lot; two hundred lines is a
#: misunderstanding, and failing loudly beats creating 2,000 rows nobody wanted.
MAX_LINES = 200

#: List markers to strip from the front of a line. Order matters only in that the
#: numbered forms are tried as one pattern.
_BULLET = re.compile(r"^\s*(?:[-–—*•·▪‣◦]|\(?\d{1,3}[.)])\s+")

#: Separators between a standard and what meeting it looks like, most specific first.
#: The spaced hyphen is deliberate: an unspaced one would split "Non-negotiable honesty"
#: and "Self-aware" down the middle, which is exactly the kind of quiet mangling this
#: module exists not to do.
_SEPARATORS = (" — ", " – ", " -- ", " - ", "\t", " | ", ": ", "—", "–")

_QUOTES = "\"'“”‘’"


@dataclass
class ParsedLine:
    """One line of the paste, and what this parser made of it."""

    line_no: int
    source: str
    value: str = ""
    desired_behavior: str = ""
    #: Set when the line cannot become a criterion. The UI shows it beside the line.
    skipped: str | None = None
    #: Set when an earlier line in this paste, or the existing library, already has it.
    duplicate_of: str | None = None

    @property
    def usable(self) -> bool:
        return self.skipped is None


@dataclass
class ParseResult:
    lines: list[ParsedLine] = field(default_factory=list)

    @property
    def ready(self) -> list[ParsedLine]:
        """The rows that would be created if the user accepted the parse as it stands."""
        return [l for l in self.lines if l.usable and not l.duplicate_of]


def _strip_quotes(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] in _QUOTES and text[-1] in _QUOTES:
        return text[1:-1].strip()
    return text


def _split(line: str) -> tuple[str, str]:
    """Split one cleaned line into (value, what meeting it looks like).

    A line with no separator is all value. That is the common case for somebody listing
    standards by name, and inventing the second half for them is the thing we will not
    do.
    """
    for sep in _SEPARATORS:
        if sep in line:
            left, right = line.split(sep, 1)
            left, right = _strip_quotes(left), _strip_quotes(right)
            # "Follow-through:" with nothing after it is still just a value.
            if left and right:
                return left, right
            if left:
                return left, ""
    return _strip_quotes(line), ""


def _key(value: str) -> str:
    """Case- and space-insensitive identity, for spotting the same standard twice."""
    return re.sub(r"\s+", " ", value).strip().casefold()


def parse_paste(text: str, *, existing: list[str] | None = None) -> ParseResult:
    """Parse pasted text into criteria rows. Pure: it reads nothing and writes nothing.

    ``existing`` is the user's current library values, so a re-paste of a list she has
    already entered is reported as duplicates rather than quietly doubling it.
    """
    seen: dict[str, str] = {_key(v): v for v in (existing or [])}
    result = ParseResult()

    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for i, raw in enumerate(raw_lines, start=1):
        if not raw.strip():
            continue

        if len(result.lines) >= MAX_LINES:
            result.lines.append(ParsedLine(
                line_no=i, source=raw.strip(),
                skipped=f"Over the {MAX_LINES}-line limit for one paste.",
            ))
            break

        cleaned = _BULLET.sub("", raw).strip()
        if not cleaned:
            continue

        value, behavior = _split(cleaned)
        row = ParsedLine(line_no=i, source=raw.strip(), value=value,
                         desired_behavior=behavior)

        if not value:
            row.skipped = "Nothing here to name a standard."
        elif len(value) > MAX_VALUE:
            # Refused, not shortened. A standard cut off mid-sentence is not her standard.
            row.skipped = (f"Longer than {MAX_VALUE} characters — shorten it and it will "
                           "go in as written.")
        elif len(behavior) > MAX_BEHAVIOR:
            row.skipped = f"The second half is longer than {MAX_BEHAVIOR} characters."
        elif _key(value) in seen:
            row.duplicate_of = seen[_key(value)]
        else:
            seen[_key(value)] = value

        result.lines.append(row)

    return result
