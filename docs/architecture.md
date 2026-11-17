# KRYteria — architecture, for approval

> **This is a frozen Milestone-1 design record from 2026-11-07, kept as written.**
> It describes what was *planned* before the agents, the API and the front end were
> built, and it has deliberately not been edited since — a design document rewritten to
> match what got built stops being evidence of anything.
>
> **It is therefore out of date on purpose.** Where it says the agent layer is "designed,
> not written", 17 tables, 95 checks, or that no virtual environment exists, read it as
> the plan rather than the state. For what KRYteria actually is now, see
> [`../README.md`](../README.md) and §4 of `report.html`: seven agents built, 34 tables,
> 1,340 checks across five suites, a React front end, and a live deployment.

Milestone 1 artifact. The build brief asks for the architecture, dependency list, schema
and plan before application code. The data layer below is **built and tested** (95 offline
checks passing); the agent layer is **designed, not written**, and is what this document
asks approval for.

---

## 1. Stack, and the departure from the brief

The brief specifies Next.js + Drizzle + Zod + Vitest. **Approved departure, 2026-11-07:**
Python/FastAPI + PydanticAI backend, React + Vite + TypeScript + Tailwind front end, served
as **one deployable application**.

| Brief | Built | Why |
|---|---|---|
| Next.js API routes | FastAPI | The agents are PydanticAI. The `gpt-6-luna` path — `OpenAIResponsesModel`, Portkey headers, the model pinning — is working code carried from HW5/HW6, including the discovery that luna rejects function tools on `/v1/chat/completions`. Rebuilding that in a TS SDK buys nothing and risks the one thing that must work. |
| Drizzle ORM | `sqlite3` + a hand-written repository (`backend/store.py`) | The product's integrity rules are enforceable as code in one audited module. An ORM would spread them across call sites. |
| Zod | Pydantic | Same role, and PydanticAI validates agent output against it natively. |
| Vitest / Playwright | `tests/test_offline.py` now; pytest + Playwright later | The offline suite runs with zero dependencies installed, which matters while the venv doesn't exist yet. |

Everything else in the brief is honoured: modular monolith, separated frontend / backend /
agent / data layers, no microservices, no paid infrastructure, one deployable app.

**Serving**: FastAPI serves the built Vite assets, so there is one process, one port, one
URL. This is what makes the 10-minute rule and the hosted deployment the same problem
solved once.

## 2. Dependency list

```
pydantic-ai-slim[openai]   agents, typed output, TestModel for free verification
fastapi + uvicorn[standard] API and static serving
python-dotenv              three-location .env resolution
pwdlib[argon2]             Argon2id passphrase hashing
itsdangerous               signed session cookies
tiktoken                   offline token counting for cost estimates
```

`pydantic-ai-slim`, not the full `pydantic-ai`: the full package pulls providers this app
never uses and can stall an install (`AGENT.MD`, Dependencies).

Front end: `react`, `react-dom`, `react-router-dom`, `tailwindcss`, `vite`, `typescript`,
`recharts`.

## 3. Data model — built

17 tables, `backend/schema.sql`. Four decisions carry the product's promises:

**Criteria are versioned, never updated.** A revision inserts a new row sharing a
`lineage_id` and supersedes the old one. There is no code path that mutates a criterion's
text. *"My standards quietly got easier to meet"* is among the most valuable things this
app can show someone, and an `UPDATE` destroys it.

**Observations carry a `kind`.** `reported_event` · `interpretation` ·
`emotional_reaction` · `missing_information` · `uncertainty`. The kind travels into the
database and onto the screen. The firewall between what happened and what someone made of
it is a column, not a prompt instruction.

**`pattern_evidence` has a `stance`.** Counter-evidence is a first-class row beside the
supporting evidence. An app that stores only what agrees with its own finding is building
a case, not holding up a mirror.

**No numeric score exists anywhere.** Not for a pattern, not for a person, not for a
relationship. `evidence_strength` is `insufficient | limited | moderate | strong`. The
column type makes the PRD's prohibition unenforceable to violate by accident.

### Guards that are code, not prose

Verified by `tests/test_offline.py` (95 checks):

| Guard | Behaviour |
|---|---|
| No evidence, no pattern | `save_pattern` raises on an empty evidence list |
| Counts are counted | `support_count` from distinct entry ids supplied, not the model's claim — five claimed, two named, gets two |
| Thin evidence downgraded | below 3 supporting entries → forced to `insufficient`, with a gap note. Still written, still shown |
| Confident findings admit doubt | `moderate`/`strong` **refused** without ≥1 alternative explanation |
| Unknown ≠ zero | unreported `cached_input_tokens` stored NULL, not 0 |
| Demo never contaminates cost | `is_simulated` steps excluded from every token and cost total |
| Delete means delete | `ON DELETE CASCADE` throughout; rows removed, not flagged |
| Export omits the hash | and the test greps the serialized blob to prove it |

## 4. Agent layer — designed, awaiting approval

A **controlled workflow**, not a delegation mesh. The orchestrator routes; specialists
return data to it and never call each other. Deliberate departure from HW5's full mesh,
for the reason the brief gives: easier to debug, cheaper, explainable. These are logical
modules in one backend, not separately deployed services.

Roster revised 2026-11-07:

```
        User brain dump — narrative + selected person + selected profile
                              ↓
                       Orchestrator
                              ↓
        ┌─────────────────────┴─────────────────────┐
     Narrative Agent                          Safety Layer
     observations, feelings,                  potential abuse, coercion,
     interpretations, uncertainty             immediate safety concerns
        └─────────────────────┬─────────────────────┘
        ┌─────────────────────┴─────────────────────┐
     Evidence Agent                           Reasoning Agent
     maps observations to                     interrogates assumptions,
     profile-specific criteria                cross-criterion trade-offs
        └─────────────────────┬─────────────────────┘
                              ↓
                   Validation + User Review
          structured output · traceable evidence · corrections
                              ↓
                     KRYteria Reflection
     evidence · questions · alternatives · user-controlled history
```

Three things in that picture are load-bearing:

**Narrative and Evidence are separate agents.** Pulling observations out of a narrative
and deciding which criteria they bear on are different jobs. Merged, an interpretation
quietly becomes a mapping.

**Safety is a peer, not a filter.** It runs alongside Narrative on the raw text —
concurrently, so it costs no extra wall-clock — never downstream of a mapping that might
have normalised something, and never gated on the selected profile. A user must never have
to list safety as a criterion before the app notices.

**Validation and User Review are code and UI, not model calls.** Pydantic validation, then
the user accepts, rejects or edits. Nothing reaches an assessment before that.

### Routing, which is also the cost control

| Situation | Agents | Model calls |
|---|---|---|
| Ordinary entry | Narrative ∥ Safety → Evidence | 3 |
| Generalising language or competing criteria | + Reasoning | 4 |
| Reflection requested, or postponement probe due | + Reflection | 5 |
| Criteria screen / Checklist Mode | Criteria only | 1 |

**Retrieval is always a tool call, never a model call.** That is the difference between a
$0.002 run and a $0.02 one, and it matters more here than in a homework script because
strangers will be using this on a hosted deployment.

Tool permissions are a filtered registry per agent, enforced in code. No agent may delete
user data, none reaches an external system, and there is no tool that sends, pays, posts,
or contacts anybody.

## 5. Safety — a separate testable layer

Runs *before* the orchestrator routes, and again on output.

- **Journal text is data, never instructions.** Entries reach the model inside a delimited,
  labelled block. An entry saying "ignore your rules" is quoted content to reflect on.
- **Risk screening.** Language indicating danger, coercion or abuse halts the reflection
  workflow and routes to real human resources. KRYteria does not counsel, does not assess
  severity, and is never presented as a crisis service.
- **Output validation.** A response that diagnoses, labels a person, states an inference as
  fact, or cites evidence that does not exist is rejected before it reaches the user.
- **Budget.** Per-account and global daily token caps, enforced by the orchestrator in
  code. This is also the answer to "what stops a bad actor burning your token budget."

Every fire writes a `safety_events` row — which is how the rubric's "show a defense
actually working" becomes a screenshot instead of a paragraph.

## 6. Open items

1. **Hosting target** not chosen. One FastAPI process, so Render/Fly/Railway all fit.
2. **Demo mode without an API key** — the brief's Definition of Done requires the demo to
   work with no live key. Design: a deterministic provider returning fixed, clearly
   labelled responses, with `is_simulated` set so nothing it produces can reach a cost
   figure. Not yet built.
3. **venv does not exist.** `pip install` must run from the Terminal panel; sandboxed Bash
   can't write the certificate pip needs. Today's 95 tests deliberately need no packages.

## 7. Plan

| Milestone | Contents | State |
|---|---|---|
| 1 Foundation | schema, store, config, env resolution, offline tests | **done** |
| 2 Agents | provider abstraction, orchestrator, 4 agents, prompt files, tool registry | next |
| 3 API + seed | FastAPI routes, synthetic demo data, demo mode | |
| 4 Front end | 6 screens, navy/ivory/sage, both themes, trace + token display | |
| 5 Safety + cost | injection tests, risk routing, budget caps, cost module | |
| 6 Delivery | deploy, fresh-clone check, README, report.html, slides.html | |

Real-user session targeted for Friday 2026-11-13; that evidence is what separates Tier 2
from Tier 3 and cannot be retrofitted.
