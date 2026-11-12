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
and texted when running ten minutes late. `reasoning.format_history` had put all three in
the prompt by id and body, so the data was there and the model did not use it.

That is the project's most load-bearing claim — *it holds your record; a chatbot cannot* —
and the first time it was measured, it did not happen. It is **deliberately unfixed**.
Editing `backend/prompts/reasoning.md` right after seeing the eval is how a benchmark
stops measuring anything. When it is changed, re-run live and keep both numbers.
