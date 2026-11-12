import { useEffect, useState } from "react";
import {
  api, type Person, type Profile, type ProfileCriterion, type Relation,
} from "../api";
import { Card, ErrorNote, Eyebrow, Pill, Spinner } from "../components/ui";
import { PersonPicker } from "../components/people";
import { placeholderFor, soleOrNone } from "../choice";

/**
 * Quick Log — the structured alternative to writing a paragraph.
 *
 * Christine, 2026-11-09: not everybody wants to type an essay after every date. Same
 * underlying data, reached by tapping instead of writing.
 *
 * Two things this gets right that the brain dump cannot:
 *
 *   It costs NO model call. The user maps the entry to their own criteria themselves,
 *   so there is nothing for an agent to infer — and a mapping the person made is more
 *   accurate than one inferred from prose, as well as free.
 *
 *   It records far less. A chip and a criterion is not a 2,000-word account, so there is
 *   less to erase later and less that ever leaves the machine.
 *
 * THE SCALE IS NOT A SCORE. "How did it land for you?" is the user's own feeling about
 * one evening, stored as words. It is never aggregated, never averaged, and never
 * attached to a person.
 */

const HAPPENED = [
  "Plans changed at short notice",
  "They followed through",
  "We had a good time",
  "A difficult conversation",
  "They didn't get back to me",
  "They checked in unprompted",
  "A boundary came up",
  "Something was said that stayed with me",
  "They showed up when it mattered",
  "Nothing much, but I noticed something",
];

const LANDED = [
  { key: "good", label: "Good" },
  { key: "fine", label: "Fine" },
  { key: "mixed", label: "Mixed" },
  { key: "off", label: "Off" },
  { key: "bad", label: "Bad" },
];

// Christine, 2026-11-12, on the old wording: "also that is fucking weird phrasing".
// "Cuts against it" is evidence-speak. These are the words a person would use.
const RELATIONS: { key: Relation; label: string; hint: string }[] = [
  { key: "supporting", label: "Shows it",
    hint: "Something here is what you're looking for." },
  { key: "contradicting", label: "Goes against it",
    hint: "Something here is the opposite of it." },
  { key: "complicating", label: "It's complicated",
    hint: "Relevant, but it cuts both ways — and that stays a real answer." },
];

export default function QuickLog({ onLogged }: { onLogged?: () => void }) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [criteria, setCriteria] = useState<ProfileCriterion[]>([]);
  const [profileId, setProfileId] = useState<number | "">("");
  const [personId, setPersonId] = useState<number | "">("");
  const [happened, setHappened] = useState<string[]>([]);
  const [landed, setLanded] = useState<string | null>(null);
  const [touches, setTouches] = useState<Record<number, Relation>>({});
  const [note, setNote] = useState("");
  const [custom, setCustom] = useState<string[]>([]);
  const [ownWhat, setOwnWhat] = useState("");
  const [savedEntryId, setSavedEntryId] = useState<number | null>(null);
  const [reading, setReading] = useState(false);
  const [reflection, setReflection] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    // Same rule as the Brain Dump: choose only where there is no choice to make.
    api.profiles().then((ps) => { setProfiles(ps); setProfileId(soleOrNone(ps)); })
      .catch(() => {});
    api.people().then((ps) => { setPeople(ps); setPersonId(soleOrNone(ps)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (profileId === "") { setCriteria([]); return; }
    api.profileCriteria(profileId)
      .then((rows) => setCriteria(rows.filter((r) => r.relevance === "relevant")))
      .catch(() => {});
    setTouches({});
  }, [profileId]);

  const ready = happened.length > 0 || landed !== null || note.trim().length > 0;

  function toggleHappened(h: string) {
    setHappened((xs) => (xs.includes(h) ? xs.filter((x) => x !== h) : [...xs, h]));
  }

  /**
   * One tap sets it, tapping the same one clears it.
   *
   * This replaced a four-state cycle on one button — tap once for supports, again for
   * cuts against, again for complicated, again for nothing. Christine, 2026-11-12:
   * "I DO NOT like that you have to multiclick... it's NOT intuitive." She is right:
   * a control that changes meaning each time you press it makes you count presses, and
   * there is no way to see the options without cycling through them. Three visible
   * buttons cost more pixels and no thought.
   */
  function setRelation(criterionId: number, relation: Relation) {
    setTouches((t) => {
      const copy = { ...t };
      const next = t[criterionId] === relation ? undefined : relation;
      if (next === undefined) delete copy[criterionId];
      else copy[criterionId] = next;
      return copy;
    });
  }

  function addOwn() {
    const v = ownWhat.trim();
    if (!v) return;
    setCustom((xs) => (xs.includes(v) ? xs : [...xs, v]));
    setHappened((xs) => (xs.includes(v) ? xs : [...xs, v]));
    setOwnWhat("");
  }

  /**
   * "Now actually read this."
   *
   * Christine, 2026-11-12: *"shouldn't we provide the user the option to ask the agent
   * to reply if the user DOES want to dig in deeper after the initial log?"* Quick Log
   * is deliberately free and instant — but choosing the fast path once should not lock
   * somebody out of the considered one. So it is offered afterwards, as a choice, and
   * never spent on their behalf.
   */
  async function readIt() {
    if (savedEntryId === null) return;
    setReading(true); setError(null);
    try {
      const r = await api.analyseEntry(savedEntryId, {
        profile_id: profileId === "" ? null : profileId,
        person_id: personId === "" ? null : personId,
      });
      setReflection(
        r.analysis?.questions?.[0]?.question
        ?? r.analysis?.reflection?.question
        ?? "KRYteria has read this. You'll find what it drew out on this entry.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReading(false);
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const entry = await fetch("/api/entries/structured", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          what_happened: happened.join(". ") || null,
          how_it_affected: landed
            ? `It landed: ${LANDED.find((l) => l.key === landed)!.label.toLowerCase()}`
            : null,
          what_expected: note.trim() || null,
          profile_id: profileId === "" ? null : profileId,
          person_id: personId === "" ? null : personId,
        }),
      }).then((r) => { if (!r.ok) throw new Error("Could not save"); return r.json(); });

      // The user's own mappings. No model call, and nothing to confirm afterwards.
      //
      // Each response is checked: fetch only rejects on a network failure, so a 4xx
      // would otherwise sail through Promise.all and let this report links it never
      // made. A success message that is not true is worse than an error.
      const results = await Promise.all(
        Object.entries(touches).map(async ([criterionId, relation]) => {
          const r = await fetch("/api/evidence-links", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              entry_id: entry.id,
              criterion_id: Number(criterionId),
              relation,
              profile_id: profileId === "" ? null : profileId,
              person_id: personId === "" ? null : personId,
            }),
          });
          return r.ok;
        }),
      );

      const wanted = results.length;
      const mapped = results.filter(Boolean).length;
      if (mapped < wanted) {
        setError(
          `Your entry is saved, but ${wanted - mapped} of ${wanted} links to your ` +
          "criteria could not be recorded. You can add them from the entry later.",
        );
      }
      // No mention of model calls. Christine, 2026-11-12: "I don't think users will
      // understand what 'no model call' means... Nobody needs to know this except me,
      // my future investors, and the professor." The cost story belongs in the trace
      // view and the report, not in the middle of somebody's evening.
      setSaved(
        mapped > 0
          ? `Logged, and linked to ${mapped} ${mapped === 1 ? "standard" : "standards"} — ${mapped === 1 ? "the one" : "the ones"} you chose.`
          : "Logged.",
      );
      setSavedEntryId(entry.id);
      setHappened([]); setLanded(null); setTouches({}); setNote("");
      setCustom([]); setOwnWhat("");
      onLogged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (saved) {
    return (
      <Card className="p-6">
        <p className="text-muted">{saved}</p>

        {reflection ? (
          <p className="voice text-ink mt-5 max-w-reading">{reflection}</p>
        ) : (
          <div className="mt-5">
            <button className="btn" onClick={readIt} disabled={reading}>
              {reading ? <Spinner label="Reading" /> : "Have KRYteria read this too"}
            </button>
            <p className="text-xs text-faint mt-2 max-w-reading leading-relaxed">
              You did the mapping yourself, which is enough. If you'd rather it looked
              for what you might not have — other standards this touches, or a question
              worth sitting with — it can.
            </p>
          </div>
        )}

        {error && <div className="mt-4"><ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote></div>}

        <button
          className="btn-quiet mt-5"
          onClick={() => { setSaved(null); setSavedEntryId(null); setReflection(null); }}
        >
          Log something else
        </button>
      </Card>
    );
  }

  return (
    <Card className="p-6 sm:p-8">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <Eyebrow>Experience journal</Eyebrow>
          <h1 className="font-serif text-2xl sm:text-3xl">A few taps is enough.</h1>
          <p className="text-muted mt-2 text-sm">
            No writing required. Pick what fits and move on.
          </p>
        </div>
        <Pill>A few taps</Pill>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <PersonPicker
          people={people}
          value={personId}
          onChange={setPersonId}
          onAdded={(p) => setPeople((xs) => [...xs, p])}
            onRemoved={(id) => setPeople((xs) => xs.filter((x) => x.id !== id))}
        />
        <div>
          <span className="eyebrow block">Which KRYteria</span>
          <select
            className="field mt-2"
            value={profileId}
            onChange={(e) => setProfileId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">
              {placeholderFor(profiles.length, "Which one? —", "Not against a profile")}
            </option>
            {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      </div>

      <div className="mt-7">
        <Eyebrow>What happened — tap any that fit</Eyebrow>
        <div className="flex flex-wrap gap-2">
          {[...HAPPENED, ...custom].map((h) => (
            <button
              key={h}
              aria-pressed={happened.includes(h)}
              onClick={() => toggleHappened(h)}
              className={`pill border transition-colors ${
                happened.includes(h)
                  ? "border-accent bg-accent/15 text-accent"
                  : "border-line text-muted hover:border-muted"
              }`}
            >
              {h}
            </button>
          ))}
        </div>
        {/* Christine, 2026-11-12: the list cannot anticipate everybody's evening.
            Anything typed here is added like any other item — and if KRYteria is asked
            to read the entry afterwards, it maps this alongside the rest. */}
        <div className="flex gap-2 mt-3">
          <input
            className="field flex-1"
            value={ownWhat}
            onChange={(e) => setOwnWhat(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addOwn(); } }}
            placeholder="Something else that happened…"
            aria-label="Add something that happened"
          />
          <button className="btn-quiet" onClick={addOwn} disabled={!ownWhat.trim()}>
            Add
          </button>
        </div>
      </div>

      <div className="mt-7">
        <Eyebrow>How did it land for you?</Eyebrow>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="How it landed">
          {LANDED.map((l) => (
            <button
              key={l.key}
              role="radio"
              aria-checked={landed === l.key}
              onClick={() => setLanded(landed === l.key ? null : l.key)}
              className={`pill border transition-colors ${
                landed === l.key
                  ? "border-accent bg-accent/15 text-accent"
                  : "border-line text-muted hover:border-muted"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-faint mt-2">
          Your feeling about this one occasion. It is never averaged and never attached
          to anybody as a rating.
        </p>
      </div>

      {criteria.length > 0 && (
        <div className="mt-7">
          <Eyebrow>Does this touch any of your criteria?</Eyebrow>
          <p className="text-xs text-faint mb-3">
            Leave a standard alone if this didn't say anything about it. Tap a choice
            again to undo it.
          </p>
          <div className="space-y-3">
            {criteria.map((c) => {
              const rel = touches[c.criterion_id];
              return (
                <div key={c.criterion_id} className="border border-line rounded-xl px-4 py-3">
                  <div className="text-sm text-ink">{c.value}</div>
                  <div
                    className="flex flex-wrap gap-2 mt-2"
                    role="radiogroup"
                    aria-label={`How this relates to ${c.value}`}
                  >
                    {RELATIONS.map((r) => {
                      const on = rel === r.key;
                      const tone =
                        r.key === "supporting" ? "border-support text-support bg-support/15"
                        : r.key === "contradicting" ? "border-contradict text-contradict bg-contradict/15"
                        : "border-complicate text-complicate bg-complicate/15";
                      return (
                        <button
                          key={r.key}
                          role="radio"
                          aria-checked={on}
                          title={r.hint}
                          onClick={() => setRelation(c.criterion_id, r.key)}
                          className={`pill border transition-colors ${
                            on ? tone : "border-line text-muted hover:border-muted"
                          }`}
                        >
                          {r.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-faint mt-3 max-w-reading leading-relaxed">
            "It's complicated" is a real answer, not a cop-out. Getting upset and then
            taking a minute and coming back to apologise is not simply good or bad.
          </p>
        </div>
      )}

      <div className="mt-7">
        <label htmlFor="ql-note" className="eyebrow block">
          Anything else <span className="text-faint normal-case tracking-normal">(optional)</span>
        </label>
        <input
          id="ql-note"
          className="field mt-2"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="One line, if there's something you want to remember"
        />
      </div>

      {error && <div className="mt-5"><ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote></div>}

      <button className="btn-primary w-full mt-7" disabled={busy || !ready} onClick={save}>
        {busy ? <Spinner label="Saving" /> : "Log it"}
      </button>

      {/* This used to say "Nothing is sent to an AI provider" flatly. Since logging
          now offers to have KRYteria read the entry afterwards, that would have become
          a promise the next screen breaks. Saying exactly when it is true keeps it
          true — and the choice stays the user's either way. */}
      <p className="text-xs text-faint mt-4 max-w-reading leading-relaxed">
        Logging this sends nothing to an AI provider. Afterwards you'll be offered the
        option to have KRYteria read it — only if you want that.
      </p>
    </Card>
  );
}
