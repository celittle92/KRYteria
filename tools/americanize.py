"""Convert British spellings to American ones in text a person reads.

Christine, 2026-11-20: *"everything was crafted using British English but I am an
American."* Correct, and it had been true since the first file.

**What this deliberately does not touch, and why each exclusion exists:**

1. **Identifiers, routes and field names.** ``acknowledgement`` is a Pydantic field that
   the prompts instruct the model to emit, the API returns, the front end reads and the
   tests assert on. Renaming it is a coordinated change across five layers whose failure
   mode is a validation error inside the *safety* step — a layer that fails open on the
   cases it exists for. The cost is an internal key nobody reads; the risk is the one
   part of this product that must not break. Same for ``/api/entries/{id}/analyse``.
2. **Archived model output** (``output/safety_results.*``, ``output/live_runs/``,
   ``output/demo_runs/``). Those are records of what a model actually said on a dated
   run. Editing them would be falsifying evidence, which is the single most corrosive
   thing anybody could do to this project's own argument.
3. **Quotations.** Christine's prompts in ``AI_prompts.md``, Alex's and Deborah's words,
   research citations and organisation names. A book's subtitle is part of its
   bibliographic record; "Rape Crisis England & Wales" is a name, not a spelling choice.
4. **The research pack.** ``data/research/*.json`` carries citations and findings
   attributed to named works. Same reason as 3.

Run ``--dry`` first. Always.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

#: British -> American. Explicit pairs, never suffix rules: a rule that turns "-ise" into
#: "-ize" also eats "surprise", "exercise" and "premise", and one that turns "-re" into
#: "-er" eats "genre", "acre" and "mediocre".
WORDS = {
    "recognise": "recognize", "recognised": "recognized", "recognises": "recognizes",
    "recognising": "recognizing", "recognisable": "recognizable",
    "analyse": "analyze", "analysed": "analyzed", "analyses": "analyzes",
    "analysing": "analyzing",
    "organise": "organize", "organised": "organized", "organises": "organizes",
    "organising": "organizing", "organisation": "organization",
    "organisations": "organizations", "organisational": "organizational",
    "realise": "realize", "realised": "realized", "realises": "realizes",
    "realising": "realizing",
    "summarise": "summarize", "summarised": "summarized", "summarises": "summarizes",
    "summarising": "summarizing",
    "minimise": "minimize", "minimised": "minimized", "minimises": "minimizes",
    "minimising": "minimizing",
    "normalise": "normalize", "normalised": "normalized", "normalises": "normalizes",
    "normalising": "normalizing",
    "apologise": "apologize", "apologised": "apologized", "apologises": "apologizes",
    "apologising": "apologizing",
    "prioritise": "prioritize", "prioritised": "prioritized",
    "prioritises": "prioritizes", "prioritising": "prioritizing",
    "categorise": "categorize", "categorised": "categorized",
    "categorises": "categorizes", "categorising": "categorizing",
    "utilise": "utilize", "utilised": "utilized",
    "specialise": "specialize", "specialised": "specialized",
    "personalise": "personalize", "personalised": "personalized",
    "personalises": "personalizes", "personalising": "personalizing",
    "authorise": "authorize", "authorised": "authorized",
    "authorisation": "authorization",
    "initialise": "initialize", "initialised": "initialized",
    "emphasise": "emphasize", "emphasised": "emphasized", "emphasises": "emphasizes",
    "emphasising": "emphasizing",
    "criticise": "criticize", "criticised": "criticized", "criticises": "criticizes",
    "criticising": "criticizing",
    "characterise": "characterize", "characterised": "characterized",
    "characterises": "characterizes", "characterising": "characterizing",
    "generalise": "generalize", "generalised": "generalized",
    "generalises": "generalizes", "generalising": "generalizing",
    "stabilise": "stabilize", "sanitise": "sanitize", "sanitised": "sanitized",
    "behaviour": "behavior", "behaviours": "behaviors", "behavioural": "behavioral",
    "behaviourally": "behaviorally",
    "colour": "color", "colours": "colors", "coloured": "colored",
    "favour": "favor", "favours": "favors", "favoured": "favored",
    "favourite": "favorite", "favourites": "favorites",
    "honour": "honor", "honours": "honors", "honoured": "honored",
    "honouring": "honoring", "honourable": "honorable",
    "labour": "labor", "laboured": "labored",
    "neighbour": "neighbor", "neighbours": "neighbors",
    "rumour": "rumor", "rumours": "rumors",
    "humour": "humor", "humoured": "humored",
    "endeavour": "endeavor", "endeavours": "endeavors",
    "centre": "center", "centres": "centers", "centred": "centered",
    "metre": "meter", "metres": "meters", "fibre": "fiber", "calibre": "caliber",
    "sombre": "somber", "spectre": "specter",
    "travelled": "traveled", "travelling": "traveling",
    "modelling": "modeling", "modelled": "modeled",
    "labelling": "labeling", "labelled": "labeled",
    "cancelled": "canceled", "cancelling": "canceling",
    "signalled": "signaled", "signalling": "signaling",
    "counselled": "counseled", "counselling": "counseling",
    "fuelled": "fueled", "fuelling": "fueling", "totalled": "totaled",
    "whilst": "while", "amongst": "among",
    "licence": "license", "licences": "licenses",
    "practise": "practice", "practised": "practiced", "practising": "practicing",
    "grey": "gray",
    "acknowledgement": "acknowledgment", "acknowledgements": "acknowledgments",
    "judgement": "judgment", "judgements": "judgments",
    "defence": "defense", "defences": "defenses",
    "offence": "offense", "offences": "offenses", "pretence": "pretense",
    "learnt": "learned", "catalogue": "catalog", "catalogues": "catalogs",
    "catalogued": "cataloged",
    "programme": "program", "programmes": "programs",
    "sceptic": "skeptic", "sceptical": "skeptical", "scepticism": "skepticism",
    "storey": "story", "storeys": "stories",
    "enrol": "enroll", "fulfil": "fulfill", "fulfils": "fulfills",
    "instalment": "installment", "skilful": "skillful", "wilful": "willful",
    "manoeuvre": "maneuver", "manoeuvres": "maneuvers",
    "artefact": "artifact", "artefacts": "artifacts",
    "enquire": "inquire", "enquiry": "inquiry", "enquiries": "inquiries",
    # The -isation nouns, which the verb list does not cover.
    "characterisation": "characterization", "generalisation": "generalization",
    "generalisations": "generalizations", "categorisation": "categorization",
    "normalisation": "normalization", "specialisation": "specialization",
    "personalisation": "personalization", "prioritisation": "prioritization",
    "minimisation": "minimization", "realisation": "realization",
    "utilisation": "utilization", "visualisation": "visualization",
    "visualisations": "visualizations", "summarisation": "summarization",
    "rationalisation": "rationalization", "rationalise": "rationalize",
    "rationalised": "rationalized", "rationalising": "rationalizing",
    "minimisations": "minimizations", "optimise": "optimize",
    "optimised": "optimized", "optimises": "optimizes", "optimising": "optimizing",
    "optimisation": "optimization",
}

#: Words that are also identifiers in this codebase — a function name, a route segment, a
#: Pydantic field. **Left alone entirely inside source files.** The dry run caught the
#: reason: `onClick={analyse}` is a React handler, and `{`/`}` do not look like code to a
#: character-level check. Renaming identifiers is a coordinated change across the API
#: path, the client, the prompts the model answers in, and the tests — worth doing
#: deliberately or not at all, never as a side effect of a spelling sweep.
IDENTIFIER_RISK = {
    "analyse", "analysed", "analyses", "analysing",
    "acknowledgement", "acknowledgements",
    "normalise", "normalised", "normalises", "normalising", "normalisation",
    "sanitise", "sanitised", "initialise", "initialised",
    "authorise", "authorised", "authorisation",
    "serialise", "serialised", "categorise", "categorised",
    # `GENERALISING` is a module constant in reasoning.py that tests import by name.
    "generalise", "generalised", "generalises", "generalising",
}

#: Never edited. Records of what a model said, and of what Christine typed.
SKIP_PATHS = (
    "output/safety_results", "output/live_runs/", "output/demo_runs/",
    "output/ab_comparison", "output/character_analysis", "data/research/",
    "data/resources", "frontend/dist/", "node_modules/", ".venv/", "__pycache__/",
    "output/user_test_notes.md", "tools/americanize.py",
)

WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")\b", re.IGNORECASE
)


def _match_case(src: str, repl: str) -> str:
    if src.isupper():
        return repl.upper()
    if src[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def _protected_spans(text: str, path: str) -> list[tuple[int, int]]:
    """Regions that are somebody's words, or a name, rather than our prose."""
    spans: list[tuple[int, int]] = []
    for m in re.finditer(r"<blockquote\b.*?</blockquote>", text, re.S | re.I):
        spans.append(m.span())
    # Markdown blockquotes: Christine's prompts, Alex's and Deborah's quotes.
    for m in re.finditer(r"^[ \t]*>.*$", text, re.M):
        spans.append(m.span())
    # URLs, paths, and anything inside backticks or <code> — identifiers, filenames,
    # commands, API routes. A route printed in the report is a fact about the software,
    # not a spelling choice.
    for m in re.finditer(
        r"`[^`\n]*`|<code>.*?</code>|https?://\S+"
        r"|\b[\w./-]+\.(?:py|ts|tsx|json|md|sql|html)\b",
        text, re.S,
    ):
        spans.append(m.span())
    return spans


def convert(text: str, path: str) -> tuple[str, int]:
    spans = _protected_spans(text, path)
    is_code = path.endswith((".py", ".ts", ".tsx", ".sql"))

    def protected(i: int) -> bool:
        return any(a <= i < b for a, b in spans)

    changed = 0

    def sub(m: re.Match) -> str:
        nonlocal changed
        word = m.group(0)
        low = word.lower()
        if protected(m.start()):
            return word
        # In source files these words are identifiers far more often than prose, and a
        # character-level test cannot tell `onClick={analyse}` from a sentence.
        if is_code and low in IDENTIFIER_RISK:
            return word
        before = text[max(0, m.start() - 1):m.start()]
        after = text[m.end():m.end() + 1]
        if low in IDENTIFIER_RISK and (
            before in ("_", ".", "/", '"', "'") or after in ("_", "(", "/")
        ):
            return word
        changed += 1
        return _match_case(word, WORDS[low])

    return WORD_RE.sub(sub, text), changed


def main() -> int:
    dry = "--dry" in sys.argv
    targets = [a for a in sys.argv[1:] if not a.startswith("-")]
    total = 0
    for rel in targets:
        p = HERE / rel
        if not p.is_file():
            print(f"  skip (not a file): {rel}")
            continue
        if any(s in rel for s in SKIP_PATHS):
            print(f"  SKIP (protected): {rel}")
            continue
        text = p.read_text(encoding="utf-8")
        new, n = convert(text, rel)
        if n:
            total += n
            print(f"  {n:4}  {rel}")
            if not dry:
                p.write_text(new, encoding="utf-8")
    print(f"\n{total} replacement(s){' (dry run, nothing written)' if dry else ''}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
