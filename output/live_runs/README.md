# Archived live runs

Every run here made **real `gpt-6-luna` calls** and cost real credits. Nothing in this
folder is regenerable for free, so **never overwrite a file in it**. A fresh run writes
`output/ab_comparison.*` or `output/safety_results.*`; copy it in here with a date before
the next run replaces it.

Demo-mode output goes to `output/demo_runs/` and is gitignored, because it makes no model
call and grades nothing.

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

Still unfixed, deliberately. The fix is not more keywords — that is the same mistake
again — but routing on something structural, which changes cost per entry and is a
decision rather than a patch.
