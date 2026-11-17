# Tokenomics

Every figure here was paid for. Nothing is modelled.

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
| | **Total** | **265** | **552,882** | **266,759** | **$0.16545** |

The first A/B run reported tokens but not cost, so the real total is marginally higher.

**A note on how that total was produced.** The first version of this table was
hand-totalled and came out $0.0064 too high. It is now summed from the rows by a script
that compares its answer against what is written. A tokenomics section whose own
arithmetic is wrong is worse than no tokenomics section, because it is the one part of a
report a reader can check in thirty seconds.

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
- Credential endpoints are throttled per handle, so the sign-in path cannot be used to
  generate load either.

---

## Stated limits

**Cache writes are not modelled.** The course publishes a $0.125/1M cache-write
surcharge; `estimate_cost` does not apply it, because the provider does not report cache
writes separately. Every figure here is therefore slightly **low on a cold cache** and
correct once warm. Saying so is cheaper than being caught by it.

**One run has no cost figure.** The first live A/B recorded tokens before the harness
recorded cost. Its scores should not be quoted either — it predates three fixes.
