# Tokenomics

Every figure here was paid for. Nothing is modeled.

The machine-readable record is [`usage_log.json`](usage_log.json); this file explains it.
Where a run's own report was later overwritten, the numbers were recovered from git
rather than remembered — the commit is named in each row.

**Model** `gpt-6-luna`, through Portkey · **$0.10 input / $0.01 cached / $0.50 output**
per 1M tokens, from MGT 409 Lecture 11's cached-token-cost table, corroborated against
this workspace's HW6 data pack. Two sources, same numbers.

---

## Everything this project has spent

| Date | Run | Calls | Input | Output | Cost |
|---|---|--:|--:|--:|--:|
| 11-11 | Brain-dump trace (5 agents) | 5 | 9,109 | 4,992 | $0.00341 |
| 11-11 | Brain-dump trace, second | 5 | 9,231 | 4,636 | $0.00324 |
| 11-11 | A/B, first live | 11 | 11,549 | 3,096 | — |
| 11-11 | A/B, after the routing fix | 12 | 16,148 | 4,451 | $0.00380 |
| 11-11 | Safety pack, 18 cases | 56 | 91,430 | 22,788 | $0.02050 |
| 11-13 | Character demo, first analysis | 58 | 139,737 | 71,213 | $0.04310 |
| 11-16 | Character demo, voice re-run | 59 | 132,542 | 71,376 | $0.04290 |
| 11-16 | One entry, to test a fix before paying for 13 | 5 | 12,865 | 8,633 | $0.00550 |
| 11-16 | Character demo, remaining 13 | 54 | 130,271 | 75,574 | $0.04300 |
| 11-17 | Reasoning evals, live | — | — | — | — |
| 11-17 | Reasoning evals, after fixing the instrument | 44 | 84,267 | 16,011 | $0.01643 |
| 11-17 | One entry traced per agent (report §4) | 5 | 10,692 | 6,146 | $0.00368 |
| 11-17 | Trace screenshot, capture lost to a page remount | 5 | 10,976 | 6,934 | $0.00456 |
| 11-17 | Trace screenshot, captured | 5 | 11,021 | 7,122 | $0.00466 |
| 11-18 | Adrian entry, after the burden-shift fix | 5 | 16,364 | 7,184 | $0.00523 |
| 11-18 | Adrian entry, after closing both new faults | 5 | 17,861 | 9,904 | $0.00674 |
| | **Total** | **334** | **704,063** | **320,060** | **$0.20675** |

**Two of the fifteen runs are not fully measured, and the total excludes what is missing rather than estimating it.** The first A/B run reported tokens but not cost. The first reasoning-eval run reported neither: the second run overwrote its artifact an hour later. So the real spend is **higher than $0.20001 by roughly $0.016 plus the A/B run's cost** — stated as a bound rather than filled in, because this file's first line is *measured, never modeled*.

**A note on how that total was produced.** The first version of this table was
hand-totaled and came out $0.0064 too high. It is now summed from the rows by a script
that compares its answer against what is written. A tokenomics section whose own
arithmetic is wrong is worse than no tokenomics section, because it is the one part of a
report a reader can check in thirty seconds.

**Two corrections on 2026-11-17, both found by audit rather than by noticing.** First,
three paid runs were missing from this table while the Total already counted them — nine
rows summing to $0.16545 under a total of $0.20199. They are restored above.

Second, `usage_log.json` held **two byte-identical rows** for the reasoning evals: 44
calls, 84,267 input, 16,011 output, $0.01643, twice. Two live runs agreeing to the digit
is not a thing that happens — but the explanation was not the obvious one. Git has the
eval artifact committed **twice that night**, at 00:07:47Z (196.01s, 37 checks passed, 6
failed) and at 01:09:27Z (12.11s, 38 passed, 5 failed). **Both were real billed runs.**
What happened was that the second run overwrote the first's artifact, and the log was
filled in by copying the surviving figures onto both rows — which turned a guess into
something that read as a measurement.

So the first run keeps its row with **every figure null**, and the total counts only what
was actually measured: **$0.20199 → $0.18556 across eleven measured runs**, with the real
spend about $0.016 higher. A number that is honestly incomplete beats one that is
confidently wrong, and this file exists to make that difference visible.

---

## What one interaction costs

| Interaction | Agents | Cost |
|---|---|--:|
| Ordinary brain dump | Narrative, Safety, Evidence, Reasoning | **$0.00208** |
| Brain dump with reflection | the above plus Reflection | **$0.00341** |

Narrative and Safety run **concurrently** on the raw text, so the wall clock is better
than the call count suggests: 72 seconds for a five-agent dump. Retrieval is always a
tool call, never a model call.

### At scale

| | Per month | 100 users | 10,000 users |
|---|--:|--:|--:|
| 12 brain dumps each, 4 agents | $0.025 | **$2.50** | **$249.62** |

---

## The cost-cutting step we took, and what it cost us

Routing *is* the cost control: three or four calls for an ordinary entry instead of five.
The first version of that routing was cheap and wrong, and both sides can be priced.

| Routing rule | Per dump | 100 users | 10,000 users | What it did |
|---|--:|--:|--:|---|
| Keyword list | $0.00136 | $1.63 | $162.88 | Skipped Reasoning on 32 of 36 corpus entries |
| Stated conclusion | $0.00208 | $2.50 | $249.62 | Runs it when the writer drew a conclusion |

**+53% per entry, and worth it.** The cheaper rule saved money by not doing the thing the
product is for: across the 36-text eval corpus the keyword gate fired 4 times, and only 3
of the 13 adversarial reasoning cases ever reached the agent they were written to test.
The suite had been grading a component that mostly never ran.

That is the honest version of "steps taken to cut cost, and whether they hurt
performance". This one hurt, measurably, and we can say by how much.

### A second saving that cost nothing

Analysis for the demo is generated **once and frozen** into `data/characters/*.json`
rather than produced on demand. The hosted deployment rebuilds its database on every boot
— a free instance has an ephemeral disk — so analysis living only in a database would be
regenerated on every restart. At $0.043 a time and a container that recycles whenever it
feels like it, that is a bill with no ceiling. Generated once, committed, served forever.

---

## What stops a bad actor burning the budget

Enforced in `backend/agents/orchestrator.py`, in code, not asked for in a prompt:

- **120,000 tokens per account per day**, checked before a run starts.
- **2,000,000 tokens globally per day.**
- **A hard ceiling of five model calls per request.** No loops, no "one more pass".
- Simulated usage never reaches the usage table, so demo mode cannot exhaust a budget or
  mask one.
- Account creation is bounded for the whole application (12/hour, 40/day). The
  per-handle counter is cleared by a successful sign-up, so a script using a fresh handle
  each time met no limit — and ~17 new accounts exhaust the 2,000,000 global daily cap.
  The cap held the money to about a dollar a day; what it could not hold was availability.
- Credential endpoints are throttled per handle, so the sign-in path cannot be used to
  generate load either.

---

## Stated limits

**Cache writes are not modeled.** The course publishes a $0.125/1M cache-write
surcharge; `estimate_cost` does not apply it, because the provider does not report cache
writes separately. Every figure here is therefore slightly **low on a cold cache** and
correct once warm. Saying so is cheaper than being caught by it.

**One run has no cost figure.** The first live A/B recorded tokens before the harness
recorded cost. Its scores should not be quoted either — it predates three fixes.
