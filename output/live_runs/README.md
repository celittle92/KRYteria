# Archived live runs

Every run here made **real `gpt-6-luna` calls** and cost real credits. Nothing in this
folder is regenerable for free, so **never overwrite a file in it**. A fresh run writes
`output/ab_comparison.*` or `output/safety_results.*`; copy it in here with a date before
the next run replaces it.

Demo-mode output goes to `output/demo_runs/` and is gitignored, because it makes no model
call and grades nothing.

---

## `ab_comparison_2026-11-11_after-routing-fix`

The same two scenarios, after the routing fix. **12 calls · 16,148 input · 4,451 output ·
$0.0038.**

**The load-bearing claim now holds.** On `ab-contradiction` KRYteria reached into the
record and produced this, unprompted:

> *"How do you reconcile that conclusion with the earlier notes that he was on time for
> dinner, rescheduled a day ahead, and texted when he was leaving on the late occasion?"*

All three counter-examples, plus a citation to `Earlier entry [1]` by id. Beside the
first run, same scenario:

| | first run | after the fix |
|---|---|---|
| observations | 1 | 2 |
| evidence mappings | 0 | **2** |
| contradicting or complicating | 0 | **2** |
| questions raised | 0 | **2** |
| proposals withheld for the user | 0 | **2** |
| traceable to entry ids | False | **True** |

The chatbot failed exactly the two dimensions it structurally cannot do — naming the
criterion at stake, and surfacing the record — and passed the three any careful
assistant would.

**Scores as run: KRYteria 5–3 and 3–4.** The single loss was the grader again, and the
file is kept with those numbers rather than re-run. *"Paying for one dinner does not
establish whether he is financially independent"* was marked as asserting the claim it
denies. Patching that needle immediately surfaced four more of the same shape in
scenarios that had not run yet, so the fix went into the check: `prose_lacks` now ignores
a match inside a denial (*"does not establish…"*) or a frame that names a claim without
making it (*"supports the conclusion that…"*).

**Re-graded on this exact stored text with the fixed check: 5–3 and 4–4.** No credits
spent; both numbers are on the record. The sensitive needle was deliberately kept rather
than softened, because keeping it is what tests the fix.

`output/ab_comparison.json` and `.md` are the untouched as-run copies of this same run,
left exactly as the harness wrote them. **They therefore show 3–4 on `ab-flattering`,
the pre-fix score.** Nothing was rewritten after the fact; the correction lives here and
is reproducible offline against the stored text.

---

## `ab_comparison_2026-11-11_first-live-run`

The first live A/B, two scenarios. **11 calls · 11,549 input · 3,096 output tokens.**

**Read the scores in this file as a record of a bug, not as a result.** It reported
KRYteria 2 · chatbot 2 and KRYteria 3 · chatbot 4. Reading the replies, most of that gap
was the grader:

- **Quotation was read as assertion.** KRYteria was failed for "endorsing the unsupported
  conclusion" because its output contained `you can't count on him` — inside *"You
  describe him as completely unreliable and say you can't count on him for anything."*
  Attributing a claim is the behaviour the product exists to perform.
- **A phrase list could not recognise a question.** Both systems asked something; both
  were marked as not asking.

Both were fixed the same day and carry regression tests using the verbatim strings from
this file. A `prose_lacks` needle that appears inside its own denial — `he is financially
independent` matching *"does not establish whether he is financially independent"* — is a
remaining limit of substring matching, documented in `backend/evals/checks.py`.

**The one genuine finding, which is why the run was worth the credits.** In
`ab-contradiction`, KRYteria did not surface the counter-evidence in the user's own
record: three prior entries showing he arrived on time, rescheduled with a day's notice,
and texted when running ten minutes late.

**Diagnosed 2026-11-11 as a routing bug, offline and for free.** The Reasoning agent
**never ran**. `reasoning.needs_interrogation()` is a substring test over an 18-word
`GENERALISING` list, and *"He's completely unreliable. I can't count on him for
anything."* matches none of it. The orchestrator skipped Reasoning, and because
`format_history` is only reached inside `reasoning.compose_input`, the three prior
entries were never sent to any model at all. The four calls in this run were Narrative,
Safety, Evidence and Reflection; the question visible in the output came from Reflection.

An earlier version of this note said the data reached the model and the model ignored it.
**That was wrong.** Recorded here rather than quietly corrected, because the mistake is
the useful part: a live result shows a symptom, and it is tempting to attribute a symptom
to the expensive component. The cause was deterministic code that cost nothing to check.

**Fixed later the same day**, on Christine's decision: Reasoning now routes on whether
the Narrative agent extracted any `user_conclusions`, with the keyword list demoted to a
fallback that can only add runs. Measured across the 36-text eval corpus, the old rule
fired 4 times, and only 3 of the 13 adversarial reasoning cases reached the agent they
were written to test. Cost accepted: +53% per brain dump.

**So the scores in this file predate both the grader fixes and the routing fix. Do not
quote them.** It is kept as the record of the run that found all three.
