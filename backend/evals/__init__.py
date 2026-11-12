"""Evaluation harness for KRYteria.

Two packs live in ``tests/evals/``:

  ``safety_evals.json``     — 18 cases from the Abuse Awareness charter, graded in BOTH
                              failure directions. Under-response (minimising a
                              disclosure) and over-response (a crisis script at an
                              ordinary bad evening) are both failures here.

  ``reasoning_evals.json``  — 13 adversarial cases, each a deliberate attempt to make the
                              model fail in a way that would still SOUND intelligent.

Until 2026-11-11 no code read either file. They were a specification nobody could run.
This package makes them executable.

WHAT A RESULT IS WORTH DEPENDS ENTIRELY ON THE MODE, and the reports say so on every
page:

  ``--mode demo``   the deterministic provider. Proves the harness and the case
                    definitions are wired up. Grades NOTHING about the real agents, and
                    the report is stamped ``evidence_value: none`` so a demo run can
                    never be mistaken for the real thing in a screenshot.

  ``--mode live``   real ``gpt-6-luna`` calls. This is the only mode whose output is
                    evidence, and the only one that costs money, so it refuses to start
                    without an explicit confirmation and prints its call count first.
"""

from .transcript import Transcript, from_brain_dump, from_prose  # noqa: F401
