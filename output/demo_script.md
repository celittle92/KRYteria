# The 2–3 minute demo video

**Optional on the assignment, and worth recording anyway.** The requirements page says a
demo video can earn the points for *It works* (15) and *Look + feel* (10) if the app will
not run for the teaching staff. It cannot earn the 5 points for *The teaching staff can
run it*. So three minutes of recording insures **25 points** against a sleeping free
instance or a laptop with the wrong Python on it.

---

## Before you press record

1. **Run it locally, not on Render.** The hosted instance sleeps and the first load takes
   about a minute; that minute is a third of the video. Local is instant.

   ```bash
   .venv/bin/python -m uvicorn backend.main:app --port 8000
   ```

2. **Live mode, not demo mode.** Demo mode returns fixed, simulated output and every step
   is labelled `is_simulated` — showing it as though it were the product would be a lie on
   camera. Live mode is the default on your machine, because `app_config` finds
   `PORTKEY_API_KEY` in the workspace `.env` one level up. Confirm before recording:
   <http://localhost:8000/api/health> should say `"mode":"live"`.

   **One brain dump with reflection costs about $0.0034.** Budget two takes: under a cent.

3. **Reset the demo so it looks untouched**, and so the entry you write on camera is the
   only new one:

   ```bash
   .venv/bin/python -m backend.seed_characters --reset
   ```

4. **Have the entry text on your clipboard.** Typing a paragraph on camera is thirty
   seconds of nothing. Copy this — it is written to make the product do its two most
   distinctive things, interrogate a stated conclusion and surface counter-evidence:

   > He cancelled again, an hour before. That is the third time and I think I have to
   > accept he is just not that interested. I keep making excuses for him. Although he
   > did text straight away and offered Thursday instead, and he has never once been late
   > when we have actually met.

5. **Screen recording on macOS:** `Cmd + Shift + 5` → *Options* → pick your microphone →
   *Record Selected Portion*, framed on the browser window only. Full screen captures your
   dock, your tabs and your notifications.

6. **Close everything else.** Notifications during a demo about a relationship journal are
   a bad look, and one of them will be from this project.

---

## The shot list — 2:50, narrated

| Time | On screen | What to say |
|---|---|---|
| **0:00–0:15** | The sign-in screen, nine characters | "KRYteria is a decision mirror. Nine invented people, each one click — no sign-up, nothing to type." Click **Catherine**. |
| **0:15–0:30** | My KRYteria: two profiles | "Her standards live in a library. Each profile selects from it and sets its own importance — the same criterion is Mandatory in one and set aside in another. That is the architecture, not a setting." |
| **0:30–1:05** | Brain Dump: paste, pick profile and person, submit | "She writes the messy version. No form, no categories." Paste, submit, and **let the spinner run** — do not cut away. "Four agents are running: one reads the narrative, one checks safety on the raw text at the same time, one maps what happened to her criteria, one interrogates the conclusion she just drew." |
| **1:05–1:40** | The analysis | "It separated what happened from what she concluded." Point at a `reported_event` beside an `interpretation`. "It mapped the evidence — and this one is *complicating*, not good or bad." Then the interrogation: "She said he is not interested. It answered with her own earlier entries." |
| **1:40–2:00** | The execution trace under the analysis | "Every run shows what each agent did, the tokens it used and what it cost. This one cost a third of a cent." |
| **2:00–2:20** | Patterns | "A pattern has to name the entries it rests on. Three support this, one cuts against it, and it says so rather than rounding." |
| **2:20–2:40** | Sign out, open **Vanessa**, her flagged entry | "Safety runs on the raw text, independent of any profile. It recognised this without being told to look — and it never labels anybody. The analysis is still recorded; it is withheld from the screen, and it says so." |
| **2:40–2:50** | My Progress | "Counts, never scores. No compatibility percentage, ever. Including the one most people have never seen: how their own standards have changed." |

---

## What to say if something goes wrong on camera

Keep it and say it. A fifteen-second "that is the free instance waking up, here it is" is
better than a cut, and far better than a fourth take. The one thing worth re-recording is
a wrong *claim*.

---

## After

Upload to Canvas with the rest. Check the audio before you close the file — a silent
screen recording is the most common way this goes wrong.
