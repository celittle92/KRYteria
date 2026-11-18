# User test — how to run it, and what to come back with

**This is the plan. `output/user_test.md` is the result**, written after the session from
what actually happened. Keep them separate: a protocol filled in ahead of time is a guess
wearing the clothes of evidence.

The rubric's Impact row (5 points) is **capped at half credit without a real person having
tried it**, and what counts is a quote, a screenshot, or a before-and-after timing. One
person, fifteen minutes, is enough.

---

## Before they arrive

**1. Decide where it runs. This matters more than it sounds.**

| | Hosted (`kryteria.onrender.com`) | Local (`uvicorn`, your machine) |
|---|---|---|
| Their data | **Erased on the next deploy** | Kept |
| Model | Live `gpt-6-luna`, real credits | Live or demo |
| First load | ~1 minute if asleep | Instant |
| Risk | You push something mid-session and wipe them | None |

**Recommended: hosted, and do not push to `main` until the session is over.** It is the
thing a stranger will actually meet, the sign-up screen now tells them nothing is kept,
and it removes "it only works on her laptop" from the result. Set a rule for yourself:
no pushes that day until you have written the notes up.

**2. Budget.** An ordinary entry is three model calls, about **$0.0021**; one that
also asks for reflection is five, about **$0.0034**. A fifteen-minute session is realistically
three to six entries — **under $0.05**. The per-account daily cap is 120,000 tokens, and a
five-agent run is roughly 17,000, so a single tester gets about **seven full entries in a
day** before the cap stops them. That is above what fifteen minutes allows, but know the
number in case they get absorbed.

**3. Pick the right person and the right subject.** The data model is domain-independent,
so the ask can be *"a situation with a colleague, a friend, or a family member where you
keep going back and forth"* rather than their marriage. Christine's own note on this: it
makes a yes far likelier, and it tests exactly the same machinery. Let them choose the
domain; do not steer them to romance because the demo does.

**4. Say the four things that protect them**, in your own words, before anything:

- Nothing they write is kept on the hosted instance; it is erased on the next update.
- Nobody else can see it, and no mechanism exists for anyone to learn they were mentioned.
- They name people by an alias they choose, never a real name.
- It is not therapy, and they can stop at any point without explaining.

**5. Ask permission for the record, specifically.** *"Can I quote you in a report for a
class? I'll use your words and not your name."* A general yes to being watched is not a
yes to being quoted.

---

## The session

Start the clock when they start reading, not when you finish explaining.

**Do not demo it.** The single most valuable thing you can learn is where somebody gets
stuck without you, and you can only learn it once. Sit on your hands. When they ask you a
question, write the question down and answer it only after they have given up on their own.

The path to put in front of them, in this order:

1. **Open one of the nine characters first** (sixty seconds). It shows them what a filled-in
   account looks like, so the empty one they make next is not frightening.
2. **Their own account** — handle and passphrase, no email. Watch what they do at the
   notice above the first field. Do they read it? Does it change what they type in?
3. **Their standards.** Offer both doors and see which they take: *Add a criterion* one at
   a time, or *Paste a list* if they already have one anywhere. This is the step that
   produced the feature; it deserves watching.
4. **One profile**, named by them, and *Add all* to fill it.
5. **One Brain Dump** about the situation they brought. Messy is correct — the product's
   claim is that they do not have to organise it first.
6. **What came back.** Can they tell, without help, which parts are what *they* said and
   which are what the agent *concluded*? That is the fact/interpretation firewall meeting
   a human for the first time.
7. **Patterns or My Progress**, if there is time.

### Five questions worth asking, at the end rather than during

1. What did you expect it to do that it didn't?
2. Was anything it said about your own situation wrong, or unfair?
3. Did it tell you anything you didn't already know — or did it tell you something you
   knew and had been avoiding?
4. Would you write in this a second time? What would have to be true?
5. What would you tell a friend this is?

Question 3 is the one that tests the actual thesis, which is that people are usually not
short of information. Ask it exactly as written; do not soften it into "was it useful?"

---

## What to write down while it happens

- **Verbatim quotes.** Their words, not your summary of their words. Two good sentences
  beat a paragraph of paraphrase.
- **Every place they hesitated**, with what was on screen.
- **Anything they asked you**, because each one is a thing the interface failed to say.
- **Time to first brain dump** — sign-up to submitted. This is the before-and-after number
  if you want one: compare it against how long they say they have been going round the
  same question in their head.
- **Screenshot of their own screen** only with permission, and check the frame for anything
  identifying before it goes in the report.

## If they disclose something real

It can happen; the subject invites it. Be a person, not a researcher: stop the session,
stay with them, and do not take notes. Nothing about a class assignment is worth more than
that. If it reaches the safety layer, note **only** that the layer behaved correctly — never
what they said.

---

## Afterwards — what `output/user_test.md` needs

Write it the same day, while you can still hear them. The skeleton:

```markdown
# User test — <first name or initial>, <date>

**Who:** <relationship to you, why they are a fair test, nothing identifying>
**Where:** hosted / local · **Domain:** work / friendship / family / romantic
**Length:** <minutes> · **Entries written:** <n> · **Cost:** $<from /api/usage>

## What happened
<Narrative, in order. Where they went, what they did without help.>

## What they said
> <verbatim quote>
> <verbatim quote>

## The number
Time from landing on the page to a submitted brain dump: <m:ss>.
<Any before-and-after comparison they offered, in their words.>

## What broke, and what nearly did
<Every hesitation and every question they asked you. Be specific. This section
being short is a finding; this section being empty means you were helping.>

## What I changed because of it
<Or: what I would change, and why it did not make this cut.>
```

**The failures are the valuable part.** A write-up where the tester sailed through and
loved everything is either untrue or a session where you helped too much — and a report
that admits two things a real person could not work out is worth more than one claiming
nobody struggled.
