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

const RELATIONS: { key: Relation; label: string }[] = [
  { key: "supporting", label: "Supports it" },
  { key: "contradicting", label: "Cuts against it" },
  { key: "complicating", label: "Complicated" },
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

  function cycleRelation(criterionId: number) {
    setTouches((t) => {
      const current = t[criterionId];
      const order: (Relation | undefined)[] = [
        undefined, "supporting", "contradicting", "complicating",
      ];
      const next = order[(order.indexOf(current) + 1) % order.length];
      const copy = { ...t };
      if (next === undefined) delete copy[criterionId];
      else copy[criterionId] = next;
      return copy;
    });
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
      setSaved(
        mapped > 0
          ? `Logged, and linked to ${mapped} ${mapped === 1 ? "criterion" : "criteria"}. No model call — you did the mapping yourself.`
          : "Logged. No model call was made.",
      );
      setHappened([]); setLanded(null); setTouches({}); setNote("");
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
        <button className="btn-quiet mt-5" onClick={() => setSaved(null)}>
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
        <Pill>No model call</Pill>
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
          {HAPPENED.map((h) => (
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
            Tap once for supports, again for cuts against, again for complicated.
          </p>
          <div className="space-y-2">
            {criteria.map((c) => {
              const rel = touches[c.criterion_id];
              return (
                <button
                  key={c.criterion_id}
                  className="choice flex items-center justify-between gap-3"
                  data-selected={Boolean(rel)}
                  onClick={() => cycleRelation(c.criterion_id)}
                >
                  <span className="text-sm text-ink">{c.value}</span>
                  <span className={`pill ${
                    rel === "supporting" ? "bg-support/15 text-support"
                    : rel === "contradicting" ? "bg-contradict/15 text-contradict"
                    : rel === "complicating" ? "bg-complicate/15 text-complicate"
                    : "text-faint"
                  }`}>
                    {rel ? RELATIONS.find((r) => r.key === rel)!.label : "Not this time"}
                  </span>
                </button>
              );
            })}
          </div>
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

      <p className="text-xs text-faint mt-4">
        Nothing is sent to an AI provider. This stays on the server until you delete it.
      </p>
    </Card>
  );
}
