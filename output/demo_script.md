# The 2–3 minute demo video

**Optional on the assignment, and worth recording anyway.** The requirements page says a
demo video can earn *It works* (15) and *Look + feel* (10). It **cannot** earn the 5 points
for *The teaching staff can run it* — those are already safe, because the hosted app is up
and a fresh clone passes in 13 seconds. So the video is not insurance against the app
failing. It is insurance against the app being **complicated**: six screens, a three-level
criteria model and five agents is a lot to meet cold, and three minutes of somebody
competent driving it is the difference between a grader seeing the architecture and a
grader seeing a form.

Rewritten 2026-11-23 against the current build. The previous version opened on "the
sign-in screen, nine characters", which has not been the front door since 20 November.

---

## Before you press record

1. **Run it locally, not on Render.** The hosted instance sleeps and the first load takes
   about a minute — a third of your video.

   ```bash
   .venv/bin/python -m uvicorn backend.main:app --port 8000
   ```

2. **Seed both demo sets**, or *See it working* lands on a 404:

   ```bash
   .venv/bin/python -m backend.seed_demo && .venv/bin/python -m backend.seed_characters
   ```

3. **Live mode, not demo mode.** Demo mode returns fixed simulated output; showing it as
   the product would be a lie on camera. Check <http://localhost:8000/api/health> says
   `"mode":"live"` before you record. **A five-agent run costs $0.0044.** Three takes is
   about a cent and a half.

4. **Have the entry text on your clipboard.** Typing a paragraph on camera is thirty dead
   seconds. Use this one — it is built to make the product do its two most distinctive
   things, interrogate a flat conclusion and answer it with her own earlier entries:

   > Greg's second-round interview turned into a third round, so still nothing. I think I
   > just have to accept this is who he is and it is not going to change. I keep telling
   > myself I am being patient but honestly I am making an exception I would not make for
   > anyone else.

   It states a conclusion, so **Reasoning fires**. Jane's postponement probe is due, so
   **Reflection fires too** — five agents, which is the run worth filming.

5. **`Cmd + Shift + 5` → Options → pick your microphone → Record Selected Portion**, framed
   on the browser window only. Full screen captures your dock and your notifications.

6. **Close everything else.** A notification during a demo about a relationship journal is
   a bad look, and one of them will be from this project.

---

## The shot list — about 2:50

| Time | On screen | What to say |
|---|---|---|
| **0:00–0:12** | The landing page | "KRYteria is a decision mirror. It compares what you said you wanted against what you have actually been writing down." Point at the line: *it never scores you, ranks you, or tells you to stay or go.* Click **See it working**. |
| **0:12–0:30** | Jane's My Progress | "This is a finished journal — ten standards, five entries, nothing typed. **Counts, never scores.** No compatibility percentage, ever." |
| **0:30–0:45** | **My KRYteria** | "Her standards live in a library. Each profile selects from it and sets *its own* importance — the same criterion is Mandatory in one profile and set aside in another. That is the architecture, not a preference." |
| **0:45–1:35** | **Brain Dump** → paste → submit → **let it run** | "She writes the messy version — no form, no categories." Submit. **The wait is about 40 seconds. Do not cut; narrate it:** "Five agents are running. One reads the narrative. One checks safety on the raw text at the same time — independent of any profile, because you should not have to file a safety concern as a dating criterion. One maps what happened onto her criteria. One interrogates the conclusion she just drew. One writes the reflection." |
| **1:35–2:05** | The analysis | "It split what happened from what she concluded." Point at a `reported_event` beside an `interpretation`. "It mapped evidence four ways — and this one is **complicating**, not good and not bad, because the app refuses to force a verdict the evidence does not support." Then the interrogation: "She said this is who he is. It answered with her own earlier entries." |
| **2:05–2:20** | **See what each part of KRYteria did** | "Every run shows what each agent did, its tokens and its latency. This one cost under half a cent. And underneath: *tool names and counts only — nothing you wrote is recorded here.*" |
| **2:20–2:40** | **Patterns** | "A pattern has to name the entries it rests on. **Three support this, one cuts against it** — and the one cutting against it is the night she laughed so hard she could not breathe. It shows you the contradiction instead of rounding it off." |
| **2:40–2:50** | **Other scenarios** → **Vanessa** → her 11 November entry | "Nine more people inside the demo. Safety ran on this one without being told to look — and it never labels anybody. The analysis is still recorded; it is withheld from the screen, and the screen says so." |

**If you want a tenth beat and have the time:** My Progress → *How your standards have
changed*. "Her definition of financial independence moved from *an income comparable to
mine* to *takes responsibility for his own obligations* — in her own words, with the date.
Most people have never seen that about themselves."

---

## The two things the rehearsal caught

1. **The wait is ~40 seconds, not 20.** Write the narration for it or you will be filming
   silence. The agent paragraph above is roughly the right length.
2. **A hedged entry runs three agents, not five.** The rehearsal entry had no flat
   conclusion, so Reasoning never fired and the trace had three rows — while the script
   said "five agents run on this." Use the entry above, in **Jane's** account, or the claim
   is false on camera.

---

## If something goes wrong while recording

Keep it and say it. Fifteen seconds of "that is the model thinking, here it comes" beats a
cut and beats a fourth take. The only thing worth re-recording is a wrong **claim**.

**Fallback if the live run misbehaves twice:** skip the brain dump, open the execution
trace that is already in Jane's account, and narrate that instead. The video is 1:50 and
loses nothing structural.

---

## After

Check the audio before you close the file — a silent screen recording is the most common
way this goes wrong. Then upload to Canvas with the repo link, `report.html` and
`slides.html`.
