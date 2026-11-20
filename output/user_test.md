# User tests — two people, and two versions of one problem

**Tester 1:** Alex M., 34, New York. A friend, not a KRYteria user, with no briefing beyond
the message in §1. Quoted by name with his explicit permission, asked separately from his
agreement to try the app.

**When:** 19 November 2026. **Where:** the hosted instance, `kryteria.onrender.com`, in
live mode against `gpt-6-luna`. **Build under test:** `2b959b5`.

**Result in one line:** he clicked every screen, wrote two journal entries, and never once
saw the thing that makes KRYteria different from a notes app — because the analysis he was
shown **could not run**, and nothing told him why.

**Tester 2:** Deborah L., 70, Massachusetts — 20 November 2026, quoted with permission.
Her session is §8, and it is short: she found a different edge of the same thing.

The raw session log, with every message in the order it was sent, is in
`output/user_test_notes.md`. This document is the write-up made from it.

---

## 1. Method, and what is wrong with it

Stated first, because a user test that hides its own weaknesses is marketing.

**He is a friend**, recruited by text, and was later thanked with a drink. That buys
goodwill, and goodwill softens criticism. The counter-measure was to ask for honesty
explicitly — *"Be honest, it's part of the user experience and will help me refine"* —
which is the cheapest available correction and not a complete one.

**The brief set no task**, and this shaped at least two of his answers. Verbatim:

> So I built an app called KRYteria. It's supposed to help people think about what they
> want in relationships and how you're valuing different aspects. It can be for work,
> family or friends too. I have some demo accounts that kind of show what the app does.
>
> I can send you the link. You have to make an account (no email required), and then can
> just play around with it. You don't have to even be serious. I just need to see that it
> works, and hear 'real user feedback'

*"Play around with it, you don't have to be serious"* is generous to the tester and hard on
the test: somebody opening an open-ended reflection tool with no goal has nothing to be
oriented **towards**. And *"it can be for work, family or friends too"* is the brief's own
words, which makes his later *"maybe make it more simple… romantic or relationships in
general"* partly a response to the pitch rather than to the product. Both are flagged again
where they bear on a finding.

**He was not demoed to.** No screen was named, no feature described, and no question of his
was answered until he had given up on it himself. The session log marks the point where
unaided use ended. This was the one thing the protocol protected hardest, and it is why
*"I don't really know where to start"* is worth anything at all.

**One tester is one tester.** Everything below is a hypothesis with a sample of one,
except the mechanism in §3, which is reproduced and deterministic.

---

## 2. What happened, in his words

| ~Time | Verbatim |
|---|---|
| T+10 | *"So I'm kind of confused of how to use it tbh"* |
| T+13 | *"I think it needs to be more straightforward with what it does in the setup process."* |
| T+13 | *"I like the idea of it being a live journal. And the quick jot option too. Like setting relationships and putting quick responses to them"* |
| T+15 | *"I've clicked through all of them. But I don't really know where to start."* |
| T+18 | *"I just did. I think the information is a bit overwhelming if I'm being honest"* (on the demo accounts) |
| T+22 | *"So maybe make it more simple… Then overtime the journal entries can be analyzed"* |
| T+24 | *"I wrote two journal entries. But I didn't really know what to do with them in the other tabs"* |
| T+27 | *"I think it would be helpful to have quick setup screen or tutorial"* |

**Read T+22 twice.** Analyzing journal entries over time, against what somebody said they
wanted, **is** KRYteria — it is the entire claim of the product. A tester proposing it as a
future feature is the strongest possible evidence that he never saw it. **You cannot ask
for what you have been shown.**

---

## 3. The root cause, reproduced

His two complaints look opposite and are the same finding:

| State | What he met | What he said |
|---|---|---|
| His own new account | Eight empty screens, no first step | *"I don't really know where to start"* |
| A demo character | 18 profiles, 90 criteria, 33 entries, 173 assessments | *"a bit overwhelming"* |

**KRYteria has no state in which a new person can orient.** Empty offers nothing to act
on; full offers everything at once. In both, the product shows its **contents** and never
its **purpose**.

The mechanism was reproduced locally in demo mode, on a throwaway account with no criteria
— his exact state — and it is deterministic rather than a matter of taste. One entry in:

| Field | Value |
|---|--:|
| `model_calls` | **2** |
| `observations` | 4 |
| evidence / mappings | **absent from the response entirely** |
| proposals, interrogations, patterns, reflection | **none** |

**Two model calls, not four.** Narrative and Safety ran. **The Evidence agent never
executed**, because there were no criteria for it to map anything against. With no
mappings there is nothing for Reasoning to interrogate and nothing for Reflection to
reflect on. Patterns additionally requires three supporting entries before it may speak.

So a person writes about being canceled on three times in a month and KRYteria returns
**four extracted observations and nothing else**. That is less than a notes app offers,
and it is what Alex was looking at when he said he did not know what to do with his
entries.

**And the app never says why.** There is no *"you have not set any criteria yet, so there
was nothing to weigh this against."* KRYteria degrades silently from a decision mirror
into a text extractor, and a reasonable person concludes the analysis feature has not been
built yet. Which is exactly what he concluded.

**The chain, every link structural rather than cosmetic:**

1. No first step → he set **no criteria**
2. No criteria → **Evidence cannot run**
3. No mappings → Reasoning, Reflection, Patterns, Progress are **structurally empty**
4. Four empty tabs → *"didn't know what to do with them in the other tabs"*
5. Never saw analysis → *"over time the journal entries can be analyzed"*, requested as a feature

**He did not fail to find the product. The product could not run.** Every distinguishing
behavior KRYteria has sits downstream of the user's criteria, and nothing in the app says
criteria come first. One missing instruction accounts for all five complaints.

---

## 4. What the fix is, and what it is not

**Predicted before the session.** The need for this change was written down before Alex
opened the link — *"I think 'MY KRYteria' should be the first page a user sees. Especially
a new user."* The session did not discover the problem. It **confirmed it, located it, and
made it precise**, which is the more useful outcome: the fix is not only which screen comes
first, but what that screen tells you to do, and what the app says when it cannot do its
job yet.

**All four changes were built the same evening**, after the session closed. The fix was
deliberately held back *during* it: a deploy erases the hosted database, and pushing would
have destroyed his account mid-test.

1. **A new account starts on My KRYteria**, not on an empty Brain Dump. Once per session
   and only from the home route, so it nudges without trapping anybody — `choice.ts`
   already states that rule for profile defaults and this follows it.
2. **An invitation, in place of an explanation.** My KRYteria now opens with *Start with
   what matters to you* — *"No standards are too high, too low, too specific, or too
   unconventional. These are your KRYteria, and you decide what matters."* The screen
   previously opened by explaining how profiles relate to one another, which is mechanism
   offered to somebody who does not yet have the point.
3. **An honest message when the analysis cannot run.** *"KRYteria can't tell you what this
   means yet — it doesn't know what matters to you. Your entry is saved."* Returned as a
   machine-readable `not_yet` on the response and shown above the short reading, so four
   observations arrive explained rather than looking like all KRYteria could manage.
4. **Demo characters open on My Progress**, not on an empty compose box in somebody else's
   account — criteria beside observed experience, which is the one view a stateless chat
   cannot produce.

**Verified by walking the path**: sign-up lands on My KRYteria with the invitation; Brain
Dump shows the gate; the gate opens; an entry with no criteria returns `not_yet` with two
model calls; a demo character opens on My Progress and can still reach Brain Dump
unimpeded. `test_an_entry_with_no_criteria_says_so_instead_of_going_quiet` keeps the third
one honest, including that the message **disappears** once a criterion exists.

**The gate is not a lock, and that was a deliberate reversal.** The first design locked
Brain Dump until three criteria existed. It was changed because the orchestrator runs
Narrative and the Safety Layer **together on the raw text, with no criteria involved** —
so writing an entry is the only route to the safety layer. A lock would have put setup in
front of somebody who opened the app at 2am because something had happened, which is the
charter's one documented exception turned inside out: *"a user must never have to mark
physical safety, consent, or freedom from coercion as a Mandatory criterion before
KRYteria recognizes a serious concern."* The prominent path is criteria; the way through
is quiet rather than absent.

**What was deliberately not done, and why.** Alex asked for *"a quick setup screen or
tutorial"*, and the request is recorded rather than implemented. "Tutorial" is the only
vocabulary most people have for "I could not orient"; it names the symptom. He had already
reconstructed the data model unprompted — *"setting relationships and putting quick
responses to them"* — so he did not need teaching, he needed starting. **A tour explains
eight screens; a first step removes the need to.** His *"make it simpler, just romantic"*
is likewise recorded and not acted on: he was designing rather than reporting, designing
around a product he had not seen, and responding to a brief that had itself offered work,
family and friends.

---

## 5. What this test did not establish

- Whether the fixes work. He tested `2b959b5`; the submitted build is different, and that
  difference has not been put in front of a user.
- Whether anybody reaches value **after** setting criteria. Nothing here tests the actual
  claim of the product, because he never got to it.
- Anything about the agents' reasoning quality, which is covered by the evaluation packs
  and the A/B rather than by this.
- Whether a stranger with a concrete task would have struggled the same way. A second test
  should give one — *"write down three things that matter to you in a friendship"* — and
  measure time-to-first-mapped-entry instead of asking for impressions.

---

## 6. An unplanned finding: the incumbent, described from inside it

Unprompted, after the feedback, Alex mentioned that he builds applications of this kind
himself. Asked whether his used agents to search for anything, he said:

> *"Not really. Claude just remembers my history of my convos i put into it."*
>
> — Alex M., 34, New York, quoted with permission

He works in marketing, not engineering, and built the tool himself. **That makes him the
person this project's positioning is about, rather than an exception to it.** §2 of the
report argues that KRYteria's real incumbent is not a competing product but a
general-purpose assistant with conversation memory. A motivated non-engineer who wanted a
reflection tool built one, and what is underneath it is conversation memory and no
structure: no extracted observations, no persistent records, nothing compared against
anything he had said he wanted.

Stated carefully, because the distinction is the point and overclaiming would weaken it:
memory across conversations is an ordinary feature of consumer assistants, not a feat. The
interesting thing is what it is **not**. A chat that remembers can recall what you said. It
cannot tell you that what you said in October contradicts what you chose in November,
because it never wrote either down as a record it could compare. That gap is what the whole
of §3 rests on, and Alex demonstrated it by living on the other side of it.

---

## 7. The honest summary

A twenty-seven-minute session with one friendly, AI-fluent, non-expert user found a defect
that two weeks of this project's own checks could not: **every automated check, both code
audits and the consistency checker passed on a build whose first-run experience could not
demonstrate the product.** Every one of those instruments verifies an artifact. None of
them asks whether a person can get started.

That is the same shape as the durability finding in §8 of the report — *documented is not
disclosed* — and it is the argument for doing this at all. The cheapest way to find out
what is wrong with a system is to watch somebody use it who does not already know how.

---

## 8. A second tester, and the opposite door

**Deborah L., 70, Massachusetts, 20 November 2026.** Not a technologist, not briefed, and
not the demographic the demo content was written for. Two findings, both small to describe
and neither one a feature request.

### She could not get out

She opened a demo account and could not find her way back to the first page. Signing out
lived in **Settings** — seven items along the navigation, under a heading about
preferences.

This is Alex's finding with the sign reversed. He could not find the way **in**: the
criteria step that everything else depends on was never offered. She could not find the way
**out**: the route existed and was never shown. Neither is a missing feature. Both are a
thing the app could do, built, documented, and invisible at the moment somebody needed it —
the same shape as the durability note and the resource decline, and now the fourth
instance.

Fixed the same day: the header carries the way out on every screen, and it reads **"Leave
demo"** on a demo account rather than "Sign out", because nobody thinks of a sample account
as something they are signed in to.

### Her first sentence about what the app is for

> **Deborah:** The website will be good for matching criteria for each other or not
>
> **Christine:** i mean it's not a couples app...is that something you took away?
>
> **Deborah:** No but if people are using it to guide their relationships it will help

**Her answer says no, and her first sentence says otherwise — and the first sentence is the
better evidence.** The follow-up was a leading question from her daughter, and the only
socially available answer to *"you didn't think that, did you?"* is no. This is the same
methodological caution as Alex's brief in §1, and it points the same way: what a tester
reaches for unprompted beats what they confirm when asked.

What she reached for was a **two-sided** reading of a product that has no second side, by
design and permanently. KRYteria forbids sharing, shared profiles, comparison, and any
mechanism that could tell a person they were written about — and the front door said
nothing about it. The sign-up screen promises a *private account*: no email, no name. That
is a claim about the **account**, not about the **product**.

**No feature follows from this.** Matching is not an unbuilt feature here, it is a
prohibition, and a tester describing it as desirable does not reopen it. What follows is
one line, where somebody deciding what to type can read it before they type:

> This is yours alone. KRYteria is not shared and has no second side — the people you write
> about are never told, and there is no version of this they can see.

That sentence was true of the system on the day it was first written. It had simply never
been said to anybody arriving.

### What this session did not establish

One short conversation, relayed through Christine rather than observed, with the tester's
daughter asking the questions. It is weaker evidence than §2 on every axis except one: she
is the only person who has used this who was not recruited for being comfortable with
software, and the two things she found were both at the very front of the product.
