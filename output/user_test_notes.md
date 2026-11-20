# User test — raw notes, written during the session

**This is the raw log. `output/user_test.md` is the write-up**, made from this afterwards.
Keep them apart: notes taken live are evidence, and a write-up made from memory an hour
later is a reconstruction. Record what was said, in the words it was said in, including
the parts that are not flattering.

Session: **2026-11-19**, tester **Alex M., 34, New York** (a friend, not a KRYteria user,
no briefing beyond the message below). Hosted instance, `kryteria.onrender.com`, live mode.

**Permission to quote: given explicitly**, by name, age and city, when asked. The ask was
made separately from the ask to try the app, which is the only way it counts — agreeing to
test something is not agreeing to be published. Use "Alex M., 34, New York"; do not
expand the surname.

Build under test: **`2b959b5`** — the one WITHOUT the first-screen fix. A new account
lands on an empty Brain Dump. `ef54da9` changes that and is deliberately unpushed, because
pushing would erase his account mid-session.

---

## What he was told, verbatim

Recorded because the brief shapes the result, and a write-up that quotes the tester
without quoting the instructions is missing half of its own evidence.

> So I built an app called KRYteria. It's supposed to help people think about what they
> want in relationships and how you're valuing different aspects. It can be for work,
> family or friends too. I have some demo accounts that kind of show what the app does.
>
> I can send you the link. You have to make an account (no email required), and then can
> just play around with it. You don't have to even be serious. I just need to see that it
> works, and hear 'real user feedback'

**Note for the write-up: this brief sets no task.** *"Play around with it, you don't have
to be serious"* is generous to the tester and hard on the test — somebody opening an
open-ended reflection tool with no goal has nothing to be oriented *towards*, so some
part of any confusion belongs to the instructions rather than to the product. That does
not make the finding below less real. It means the finding has two causes and the report
should say which is which rather than claiming the whole of it for the design.

---

## Timeline

**T+~10 min — first unprompted reaction, verbatim:**

> So I'm kind of confused of how to use it tbh

No prompting, no questions asked of him first. He reached this on his own, which is the
thing the protocol's "do not demo it" rule exists to protect.

**What the build he is on does at that moment:** a new account with no criteria lands on
Brain Dump — *"Tell us what happened. No forms. No required categories."* — with nothing
to map an entry against. The screen that would tell him what the app is for, My KRYteria,
is the third item in the nav and nothing points at it.

**T+~11 min — first intervention, verbatim.** Recorded because everything after this point
is prompted rather than unaided, and the write-up has to say where that line falls:

> Ok, tell me more
>
> (Be honest, it's part of the user experience and will help me refine)

Deliberately non-leading — it names no screen and suggests no answer, so whatever comes
back is still his. The parenthetical is doing real work: a friend testing a friend's
project softens criticism by default, and explicitly licensing honesty is the cheapest
available correction for that. It will not, on its own, establish **which screen** he was
on, so expect to need one more question.

**T+~13 min — the finding, verbatim.** Prompted only by *"tell me more"*; no screen was
named to him and no feature was described:

> I think it needs to be more straightforward with what it does in the setup process.
>
> I like the idea of it being a live journal. And the quick jot option too. Like setting
> relationships and putting quick responses to them

**Three separate results in four lines, and they point different ways.**

1. **The defect is located, and it is narrower than "needs onboarding".** Not the layout,
   not the model, not the vocabulary — **the setup process does not say what the app
   does**. That matches what the screens actually do: My KRYteria opens with *"Different
   things matter for different kinds of connection. Each profile is its own configuration
   — changing one never changes another,"* which explains the **mechanism** to somebody
   who already has the **point**. A first-timer needs the point first.
2. **The concept is legible once he is in it.** *"Setting relationships and putting quick
   responses to them"* is an accurate description of people, profiles and observations,
   reached without being told. This is the answer to "have I overcomplicated this" and it
   came from a stranger rather than from the author: the model survived contact.
3. **He names the live journal and the quick-jot option as the parts he likes** — the
   primary interaction and the low-effort door into it. Nothing in his reply mentions
   criteria, evidence mapping or assessment, which is worth recording honestly: the parts
   he volunteered are the parts that ask least of him.

**What this does NOT yet establish:** whether he ever reached an analysed entry, and
therefore whether the thing that distinguishes KRYteria from a journalling app was ever
visible to him. Ask before closing the session.

**T+~15 min — the decisive line.** Asked which screens he had looked at:

> I've clicked through all of them. But I don't really know where to start.

**This rules out the explanation everybody reaches for first.** It is not discoverability
and it is not navigation. He found every screen, including My KRYteria, and was no better
off. The app does not have a findability problem; it has an **ordering** problem.

**It also means the fix already committed is necessary and not sufficient, which is worth
stating plainly rather than quietly widening the change.** `ef54da9` lands a new account
on My KRYteria instead of an empty Brain Dump. He reached My KRYteria under his own steam
and still did not know where to start, so landing him there faster would not have saved
him. The screen he needed to arrive on also has to tell him **what to do first**.

**What he actually met:** eight equally weighted tabs, every one of them empty, none
marked as the beginning. Four of them — Journal, Patterns, Reflection, My Progress —
*cannot* do anything until entries exist, so an empty account is mostly doors that open
onto nothing. No screen says "start here", and the one that should opens by explaining
how profiles relate to each other.

**The defect, stated for the report:** *KRYteria presents a new account with eight doors
and no first step.* Both of his messages say the same thing in different words — "more
straightforward with what it does in the setup process", "I don't really know where to
start" — and the second is the more actionable, because a first step is a smaller and
more testable thing to add than an explanation of what the app is.

**T+~18 min — the demo accounts.** Asked whether he had looked at any:

> I just did. I think the information is a bit overwhelming if I'm being honest

**Put beside the earlier line, this is one finding rather than two, and it is the finding
of the session:**

| State | What he met | What he said |
|---|---|---|
| His own new account | Eight empty screens, no first step | *"I don't really know where to start"* |
| A demo character | Eighteen profiles, ninety criteria, thirty-three entries, a hundred and seventy-three assessments | *"a bit overwhelming"* |

**KRYteria has no state in which a new person can orient.** Empty gives them nothing to
act on; full gives them everything at once. Neither shows the one thing the app does. The
two complaints look opposite and have the same cause — in both states the product shows
its *contents* and never its *purpose*.

**A specific, verified cause for the demo half.** Opening a character signs in and routes
to `/`, which is **Brain Dump** — an empty compose box in somebody else's account. The
screens that actually demonstrate the product (Journal with its analysis, Patterns, My
Progress) are elsewhere in the nav and he had to find them himself, arriving at each one
cold and fully populated. Confirmed by opening `?demo=theintentionalist` during this
session: it lands on *"Tell us what happened."*

**So a demo visitor meets the least illustrative screen first and the densest screens
second.** That ordering is backwards for the one job the demo accounts exist to do.

**What this does not mean.** The demo accounts are dense deliberately — patterns across
time cannot be shown without many entries, and thinning them would destroy the thing they
exist to prove. The fix is an **entry point**, not less content: land a demo visitor
somewhere that shows one finding, and let them go deeper if they want to.

**T+~22 min — unprompted product suggestion:**

> So maybe make it more simple. Like have it be about romantic relationship analysis or
> relationships in general.
>
> The journaling is a cool idea. And making a way to journal about specific people easier.
>
> Then overtime the journal entries can be analyzed

**Read the last line twice. He is asking for the product.** Analysing journal entries over
time against what somebody said they wanted *is* KRYteria; it is the whole claim. A tester
proposing it as a future feature is the strongest possible evidence that **he never saw
it** — you cannot ask for what you have been shown.

Note also, honestly: *"romantic or relationships in general"* is partly a response to the
brief, which said *"It can be for work, family or friends too."* That is the second time
the instructions shaped the result. The signal worth keeping is that **the pitch and the
first screen did not agree on what this is for**, which is a copy problem and one the
project is already committed to — the rules say romantic leads, with the data model
staying domain-agnostic underneath.

**T+~24 min — and here is why he never saw it:**

> I wrote two journal entries. But I didn't really know what to do with them in the other
> tabs

**The chain is now complete, and every link is structural rather than cosmetic:**

1. No first step, so he **never set any criteria**.
2. With no criteria, the Evidence agent has nothing to map an entry against. His two
   entries could produce observations and *nothing else* — no mappings, no proposed
   statuses, no unsettled notes about standards he never named.
3. Patterns needs three supporting entries before it may say anything at all
   (`MIN_SUPPORT`). My Progress compares criteria against experiences and he had one half
   of that. Reflection had no assessment to reflect on.
4. So the four tabs downstream of writing were **structurally empty for him**, and he
   correctly reported that he did not know what to do with them.

**He did not fail to find the product. The product could not run.** Every distinguishing
behaviour KRYteria has is downstream of the user's criteria, and nothing in the app told
him criteria came first. That is the single root cause of all four complaints in this
session, and it is one missing instruction deep.

### Reproduced locally — what his two entries actually returned

Run in demo mode on a throwaway account with **no criteria**, which is the state he was
in. Free, no credits, account deleted afterwards. The entry used:

> *"Sam cancelled again on Friday, third time this month. He said work ran over. I keep
> telling myself it is fine but I am starting to wonder whether I matter much here."*

What came back:

| Field | Value |
|---|--:|
| `model_calls` | **2** |
| `observations` | 4 |
| `missing_information` | 1 |
| `uncertainties` | 1 |
| evidence / mappings | **absent from the response entirely** |
| proposals, interrogations, patterns, reflection | **none** |

**Two model calls, not four.** Narrative and Safety ran; **the Evidence agent never
executed**, because there are no criteria for it to map anything to. With no mappings
there is nothing for Reasoning to interrogate and nothing for Reflection to reflect on.

So a person writes about being cancelled on three times in a month and KRYteria hands back
**four extracted observations and nothing else** — no comparison, no unsettled note, no
question. That is strictly less than a notes app would give them, and it is the output the
tester was looking at when he said he did not know what to do with his entries.

**And it never says why.** There is no "you haven't set any criteria yet, so there was
nothing to weigh this against." The app degrades silently from a decision mirror to a text
extractor, and the user is left to conclude — reasonably — that analysing entries over
time is a feature that has not been built.

**This is the defect to fix, and it is two sentences of copy plus a routing change.** The
honest message at that moment is the whole product in one line: *"KRYteria can't tell you
what this means yet — it doesn't know what matters to you. Start with My KRYteria."*

**T+~27 min — his own proposed fix:**

> I think it would be helpful to have quick setup screen or tutorial

**Worth recording, and worth not taking literally.** "Tutorial" is what people ask for when
they cannot orient; it names the symptom in the only vocabulary most users have for it. His
own evidence points at something smaller and better: he did not need to be *taught* the
app, he needed to be *started*. He had already worked out what it did — *"setting
relationships and putting quick responses to them"* — before he asked for a tutorial.

A tour explains eight screens. A first step removes the need to. Build the first step, and
note the tutorial request as the thing it is answering.

**Prediction logged before the session, by Christine, unprompted by any of this:** *"I
think 'MY KRYteria' should be the first page a user sees. Especially a new user."* That was
written down before Alex opened the link. The session did not discover the problem — it
**confirmed it and made it precise**, which is the more useful outcome: the fix is not only
*which screen comes first* but *what that screen tells you to do*, and *what the app says
when it cannot do its job yet*.

---

## Session close

Thanked, and offered a drink at a concert they are both going to. Recorded for honesty:
he is a friend, and the write-up says so rather than implying a recruited stranger.

### Afterwards — who the tester turned out to be

Unprompted, after the feedback was given:

> I make apps like this at work.
> Like my health therapy app I use when I'm freaking out over a cold

Asked whether it used agents to search for symptoms:

> Not really. Claude just remembers my history of my convos i put into it

**Correction, made the same day and left visible rather than edited away.** The first
version of this note said he "builds in this category professionally" and called him
somebody "who ships reflection apps". **That was wrong.** Christine supplied the fact:
**he works in marketing for a physical therapy and fitness equipment company, not in
engineering.** "I make apps like this at work" means internal tools he has built himself,
with AI assistance — not a product career. The original reading inflated his authority
from one ambiguous sentence, which is exactly the trait-leap this project grades its own
agents for, committed here by its author about a human being.

**The accurate reading, which is still worth something.** He is an **AI-fluent
non-engineer** who has built working tools of his own and still could not work out where
to start. That is a meaningfully harder finding than a novice getting lost — this is
somebody with the confidence and vocabulary to poke at an unfamiliar app, who clicked
every screen and wrote two entries before giving up on the point of it. It is not,
however, the opinion of a professional in the field, and the write-up must not borrow
authority the fact does not support.

**It is also, unprompted, the strongest external evidence the project has for its own
positioning — and the correction above makes it stronger, not weaker.** Slide 3 claims
*the real incumbent is not a product*: that what KRYteria actually competes with is a
general-purpose model with conversation memory. Alex is a **literal instance of that
claim**. A motivated non-engineer, wanting a reflection tool, built one — and what is
underneath it is **conversation memory and no structure**. No extracted observations, no
persistent records, nothing compared against anything he had said he wanted.

Had he been a professional engineer, he would have been an unusual case. Being a
marketer who built his own thing with Claude makes him **exactly the person the incumbent
serves**, which is the argument the report is making. He reached for the incumbent without
being asked about it, and described it accurately, with no stake in this project.

**And it is the lens that explains his "make it simpler".** Somebody whose working model of
this product category is *talk to it and it remembers* will experience *name your standards
first* as friction, because in his architecture there is nothing to name them **to**. That
does not weaken the finding — he genuinely could not start — but it means "simpler" should
be read as *"this asks for structure before it gives anything back"*, which is the same
root cause as everything else in this session, not a separate request to drop the model.

**Consent for this part: asked separately, scoped, and GRANTED.** He agreed to the two
lines about building apps at work and about Claude remembering his conversation history,
and **declined nothing except the health application**, which is excluded by his own
instruction and must not appear in the report, the deck, or any screenshot of these notes.
Attribution stays **Alex M., 34, New York**.
The earlier yes covered his feedback on KRYteria; quoting him about what he builds is a
different thing and was put to him on its own, verbatim:

> Can I use your quote about you making apps like this at work and that Claude remembers
> your history of convos? Nothing about a health therapy app specifically. I'm also only
> attributing you as Alex M., 34, New York

Correctly scoped — it names what will be used, excludes the health app, and states the
attribution. **Nothing from this section goes in the report until he answers.** If he
declines, the positioning point survives without him; it just loses its witness.

**One factual guard for the write-up.** *"Claude just remembers my history of my convos"*
is a description of an ordinary product feature — consumer assistants carry memory across
conversations — not of anything unusual he built. The report should not present it as a
technical feat or imply he engineered persistence. The interesting thing is **what it is
not**: memory of a conversation is not a record of extracted observations mapped to
criteria somebody set, which is the distinction the whole of §3 rests on.

---

## Still to collect before this can be written up

- [ ] Which screen he was on when he said it, and what he expected instead.
- [ ] Whether he found My KRYteria on his own, and how long that took.
- [ ] One quote worth printing, **plus explicit permission to print it** — a yes to
      trying the app is not a yes to being quoted.
- [ ] A screenshot of whatever confused him, if he will take one.
- [ ] Roughly how long before he could say what the app was for.

**Time-critical:** his account is erased by the next deploy. Collect anything worth
keeping before `ef54da9` is pushed.
