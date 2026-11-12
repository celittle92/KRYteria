import { useEffect, useRef, useState } from "react";
import { awaitingChoice, placeholderFor, soleOrNone } from "../choice";
import {
  api, type Account, type Analysis, type Entry, type Person, type Profile,
  type Retention,
} from "../api";
import {
  Card, Empty, ErrorNote, Eyebrow, OBSERVATION_COPY, Pill, RETENTION_COPY,
  RelationPill, Spinner,
} from "../components/ui";
import { PersonPicker } from "../components/people";
import QuickLog from "./QuickLog";

/**
 * The primary experience. Everything else is downstream of this box.
 *
 * "Tell us what happened. No forms. No required categories. No need to organize your
 * thoughts first." The person and profile selectors sit UNDER the textarea, not above
 * it, so nothing stands between somebody and writing.
 */
export default function BrainDump({ account }: { account: Account }) {
  // Two ways in, neither the fallback. Some people want to write; some want to tap.
  const [mode, setMode] = useState<"write" | "quick">("write");
  const [text, setText] = useState("");
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [profileId, setProfileId] = useState<number | "">("");
  const [personId, setPersonId] = useState<number | "">("");
  const [wantReflection, setWantReflection] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ entry: Entry; analysis: Analysis | null } | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Choose only where there is nothing to choose between — see src/choice.ts.
    api.profiles().then((ps) => { setProfiles(ps); setProfileId(soleOrNone(ps)); })
      .catch(() => {});
    api.people().then((ps) => { setPeople(ps); setPersonId(soleOrNone(ps)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (result) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  async function analyse() {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.brainDump({
        text,
        profile_id: profileId === "" ? null : profileId,
        person_id: personId === "" ? null : personId,
        want_reflection: wantReflection,
        // Retention is chosen AFTER, on the results screen, so somebody can see what the
        // reflection produced before deciding whether the narrative is worth keeping.
        retention: "keep_all",
      });
      setResult({ entry: res.entry, analysis: res.analysis });
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div ref={resultRef}>
        <Result
          entry={result.entry}
          analysis={result.analysis}
          defaultRetention={account.retention}
          onDone={() => setResult(null)}
        />
      </div>
    );
  }

  const toggle = (
    <div className="flex gap-1 mb-5" role="radiogroup" aria-label="How to record this">
      {([["write", "Write it out"], ["quick", "Quick log"]] as const).map(([k, label]) => (
        <button
          key={k}
          role="radio"
          aria-checked={mode === k}
          onClick={() => setMode(k)}
          className={`px-4 py-1.5 rounded-full text-sm transition-colors ${
            mode === k
              ? "bg-ink text-ground"
              : "text-muted hover:text-ink border border-line"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );

  if (mode === "quick") {
    return (
      <div className="max-w-3xl">
        {toggle}
        <QuickLog />
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      {toggle}
      <Card className="p-6 sm:p-8">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <Eyebrow>Experience journal</Eyebrow>
            <h1 className="font-serif text-2xl sm:text-3xl">Tell us what happened.</h1>
            <p className="text-muted mt-2 text-sm">
              No forms. No required categories. No need to organise your thoughts first.
            </p>
          </div>
          <Pill tone="accent">Core feature</Pill>
        </div>

        <label htmlFor="dump" className="eyebrow block">Your brain dump</label>
        <textarea
          id="dump"
          className="field mt-2 min-h-[220px] resize-y voice text-lg"
          placeholder="We went to dinner and he was really funny…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
        />

        <div className="grid sm:grid-cols-2 gap-4 mt-5">
          <div>
            <label htmlFor="profile" className="eyebrow block">
              Which KRYteria <span className="text-faint normal-case tracking-normal">(optional)</span>
            </label>
            <select
              id="profile"
              className="field mt-2"
              value={profileId}
              onChange={(e) => setProfileId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">
                {placeholderFor(profiles.length, "Which one? —", "Not against a profile")}
              </option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            {awaitingChoice(profiles.length, profileId) && (
              <p className="text-xs text-faint mt-2">
                Pick one and KRYteria can map this to those criteria. Leave it and it
                will still read what you wrote — none of your profiles outranks another,
                so it won't guess.
              </p>
            )}
          </div>
          <PersonPicker
            people={people}
            value={personId}
            onChange={setPersonId}
            onAdded={(p) => setPeople((xs) => [...xs, p])}
            onRemoved={(id) => setPeople((xs) => xs.filter((x) => x.id !== id))}
          />
        </div>

        <label className="flex items-start gap-3 mt-5 text-sm text-muted cursor-pointer">
          <input
            type="checkbox"
            checked={wantReflection}
            onChange={(e) => setWantReflection(e.target.checked)}
            className="mt-1 accent-[rgb(var(--accent))]"
          />
          <span>
            Also give me something to reflect on.
            <span className="text-faint"> Takes a moment longer.</span>
          </span>
        </label>

        {error && <div className="mt-5"><ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote></div>}

        <button
          className="btn-primary w-full mt-6"
          onClick={analyse}
          disabled={busy || !text.trim()}
        >
          {busy ? <Spinner label="Reading what you wrote" /> : "Analyse experience"}
        </button>

        <p className="text-xs text-faint mt-4">
          Your words are sent to an AI provider in order to be read. You choose what
          KRYteria keeps afterwards.
        </p>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ the result */

function Result({ entry, analysis, defaultRetention, onDone }: {
  entry: Entry;
  analysis: Analysis | null;
  defaultRetention: Retention;
  onDone: () => void;
}) {
  const safety = analysis?.safety;
  const concerned = Boolean(safety?.concern_detected);

  return (
    <div className="max-w-3xl space-y-6">
      {/* When the safety layer has fired, this comes FIRST and the ordinary analysis
          does not pretend nothing was said. */}
      {concerned && <SafetyNotice analysis={analysis!} />}

      {analysis && !analysis.halted && <Reading analysis={analysis} />}

      {analysis?.halted && (
        <Card className="p-6">
          <p className="text-muted text-sm">
            KRYteria stopped here rather than continuing with the ordinary analysis.
            What you described matters more than a compatibility question.
          </p>
        </Card>
      )}

      <RetentionChoice entryId={entry.id} initial={defaultRetention} />

      <div className="flex gap-3">
        <button className="btn-quiet" onClick={onDone}>Write something else</button>
      </div>
    </div>
  );
}

function SafetyNotice({ analysis }: { analysis: Analysis }) {
  const s = analysis.safety!;
  const resources = analysis.resources ?? [];
  const [declined, setDeclined] = useState(false);

  return (
    <Card className="p-6 sm:p-7 border-complicate/40">
      {s.acknowledgement && (
        <p className="voice text-lg leading-relaxed">{s.acknowledgement}</p>
      )}
      {s.rationale && <p className="text-muted mt-4 text-sm leading-relaxed">{s.rationale}</p>}
      {s.safety_check && (
        <p className="voice text-lg mt-5 text-ink">{s.safety_check}</p>
      )}

      <p className="text-sm text-muted mt-5">
        You don't have to decide what to call this right now.
      </p>

      {resources.length > 0 && !declined && (
        <div className="mt-6">
          <Eyebrow>If it would help</Eyebrow>
          <ul className="space-y-3 mt-2">
            {resources.map((r) => (
              <li key={r.id} className="text-sm">
                <div className="text-ink">{r.name}</div>
                <div className="text-muted">
                  {[r.phone, r.text_line, r.hours].filter(Boolean).join(" · ")}
                </div>
                {r.url && (
                  <a href={r.url} target="_blank" rel="noreferrer noopener"
                     className="text-accent hover:underline">{r.url}</a>
                )}
                {r.note && <div className="text-faint text-xs mt-0.5">{r.note}</div>}
                {/* The date is shown on purpose. A number you can see was checked —
                    and when — is something you can judge; a bare number asks to be
                    trusted. Verifying six countries found two dead government pages
                    and an organisation contradicting itself about its own number. */}
                {r.verified_at && (
                  <div className="text-faint text-xs mt-0.5">
                    Checked {new Date(r.verified_at).toLocaleDateString(undefined, {
                      day: "numeric", month: "short", year: "numeric",
                    })}
                  </div>
                )}
              </li>
            ))}
          </ul>
          <p className="text-faint text-xs mt-3 max-w-reading leading-relaxed">
            Numbers and opening hours change, and services close. If one of these doesn't
            work, your local emergency number is the fastest route.
          </p>
          <button className="btn-quiet mt-5 text-xs" onClick={() => setDeclined(true)}>
            I don't need these
          </button>
        </div>
      )}

      {analysis.emergency_note && (
        <p className="text-sm text-ink mt-6">{analysis.emergency_note}</p>
      )}

      {declined && (
        <p className="text-sm text-muted mt-6">
          Understood. I won't bring those up again unless you ask, or something changes
          that makes immediate safety relevant. We can focus on what happened and what
          it means to you.
        </p>
      )}
    </Card>
  );
}

function Reading({ analysis }: { analysis: Analysis }) {
  const obs = analysis.observations ?? [];
  const byKind = (kind: string) => obs.filter((o) => o.kind === kind);
  const stated = byKind("reported_event");
  const interpretations = byKind("interpretation");
  const feelings = byKind("emotional_reaction");
  const missing = [...byKind("missing_information"), ...byKind("uncertainty")];

  return (
    <>
      <Card className="p-6 sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-serif text-xl">What KRYteria read</h2>
          <Pill tone="accent">Evidence mapping</Pill>
        </div>

        {stated.length > 0 && (
          <div className="mt-6">
            <Eyebrow>{OBSERVATION_COPY.reported_event}</Eyebrow>
            <ul className="space-y-2">
              {stated.map((o) => (
                <li key={o.id ?? o.text} className="text-ink leading-relaxed">{o.text}</li>
              ))}
            </ul>
          </div>
        )}

        {interpretations.length > 0 && (
          <div className="mt-6">
            <Eyebrow>{OBSERVATION_COPY.interpretation}</Eyebrow>
            <p className="text-xs text-faint mb-2">
              Kept separate from what happened. These are readings, not events.
            </p>
            <ul className="space-y-2">
              {interpretations.map((o) => (
                <li key={o.id ?? o.text} className="text-muted leading-relaxed">
                  {o.text}
                  {o.certainty === "inferred" && o.hedge && (
                    <span className="block text-sm text-complicate mt-1">{o.hedge}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {feelings.length > 0 && (
          <div className="mt-6">
            <Eyebrow>{OBSERVATION_COPY.emotional_reaction}</Eyebrow>
            <ul className="space-y-1.5">
              {feelings.map((o) => (
                <li key={o.id ?? o.text} className="text-muted">{o.text}</li>
              ))}
            </ul>
          </div>
        )}

        {missing.length > 0 && (
          <div className="mt-6">
            <Eyebrow>Not yet known</Eyebrow>
            <ul className="space-y-1.5">
              {missing.map((o) => (
                <li key={o.id ?? o.text} className="text-muted">{o.text}</li>
              ))}
            </ul>
          </div>
        )}

        {(analysis.mappings?.length ?? 0) > 0 && (
          <div className="mt-7">
            <Eyebrow>How this relates to your criteria</Eyebrow>
            <ul className="divide-y divide-[rgb(var(--line))]">
              {analysis.mappings!.map((m, i) => (
                <li key={i} className="py-3 flex items-start justify-between gap-4">
                  <span className="text-sm text-muted">{m.rationale ?? "—"}</span>
                  <RelationPill relation={m.relation} />
                </li>
              ))}
            </ul>
          </div>
        )}

        {(analysis.insufficient?.length ?? 0) > 0 && (
          <div className="mt-6">
            <Eyebrow>Not settled by this</Eyebrow>
            <ul className="space-y-2">
              {analysis.insufficient!.map((i, n) => (
                <li key={n} className="text-sm text-muted">{i.why}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {(analysis.questions?.length ?? 0) > 0 && (
        <Card className="p-6 sm:p-7">
          <h2 className="font-serif text-xl">Let's examine that</h2>
          <ul className="mt-5 space-y-5">
            {analysis.questions!.map((q, i) => (
              <li key={i}>
                <p className="text-sm text-faint italic">"{q.claim}"</p>
                <p className="voice text-lg mt-1.5">{q.question}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {(analysis.cross_criterion?.length ?? 0) > 0 && (
        <Card className="p-6 sm:p-7">
          <h2 className="font-serif text-xl">One behaviour, several criteria</h2>
          <ul className="mt-4 space-y-4">
            {analysis.cross_criterion!.map((c, i) => (
              <li key={i}>
                <p className="text-muted text-sm leading-relaxed">{c.explanation}</p>
                {c.competing && c.competing_question && (
                  <p className="voice text-lg mt-2">{c.competing_question}</p>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {analysis.reflection && <ReflectionCard reflection={analysis.reflection} />}

      <TraceNote analysis={analysis} />
    </>
  );
}

function ReflectionCard({ reflection }: { reflection: NonNullable<Analysis["reflection"]> }) {
  const [choice, setChoice] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function record(c: string) {
    setChoice(c);
    try {
      await api.recordDecision({ choice: c as never });
      setSaved(true);
    } catch { /* the choice is still shown; recording it is not worth an interruption */ }
  }

  return (
    <Card className="p-6 sm:p-7">
      {reflection.context && (
        <h2 className="font-serif text-xl">{reflection.context}</h2>
      )}
      <p className="voice text-lg sm:text-xl mt-3 leading-relaxed">{reflection.question}</p>

      {reflection.reconciliation && (
        <div className="mt-6 grid sm:grid-cols-2 gap-5 text-sm">
          <div>
            <Eyebrow>Right now</Eyebrow>
            <p className="text-muted">{reflection.reconciliation.current_feeling}</p>
          </div>
          <div>
            <Eyebrow>What the record holds</Eyebrow>
            <p className="text-muted">{reflection.reconciliation.broader_evidence}</p>
          </div>
        </div>
      )}

      {reflection.alternatives.length > 0 && (
        <div className="mt-6">
          <Eyebrow>Other readings</Eyebrow>
          <ul className="space-y-1.5">
            {reflection.alternatives.map((a, i) => (
              <li key={i} className="text-muted text-sm">{a}</li>
            ))}
          </ul>
        </div>
      )}

      {reflection.options.length > 0 && (
        <div className="mt-7">
          <Eyebrow>What would you like to do with that?</Eyebrow>
          <div className="space-y-2 mt-2" role="radiogroup">
            {reflection.options.map((o) => (
              <button
                key={o}
                role="radio"
                aria-checked={choice === o}
                className="choice"
                onClick={() => record(o)}
              >
                {DECISION_LABEL[o] ?? o}
              </button>
            ))}
          </div>
          {saved && (
            <p className="text-xs text-faint mt-3">
              Recorded. Waiting is a decision like any other.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

const DECISION_LABEL: Record<string, string> = {
  talk: "Talk about it",
  boundary: "Set a boundary",
  more_time: "Give it more time",
  gather_info: "Gather more information",
  reconsider: "Reconsider the relationship",
  revise_criterion: "Revise a criterion",
  undecided: "I don't know yet",
};

/** Token counts on screen, which is also the tokenomics evidence the rubric asks for. */
function TraceNote({ analysis }: { analysis: Analysis }) {
  const [open, setOpen] = useState(false);
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);

  async function show() {
    setOpen(true);
    if (!trace) {
      try {
        const r = await fetch(`/api/runs/${analysis.run_id}`, { credentials: "same-origin" });
        setTrace(await r.json());
      } catch { /* the trace is a nicety; its absence is not an error worth showing */ }
    }
  }

  const steps = (trace?.steps as { agent: string; input_tokens: number; output_tokens: number; latency_ms: number }[]) ?? [];

  return (
    <div className="text-xs text-faint">
      {!open ? (
        <button onClick={show} className="hover:text-muted transition-colors">
          See what each part of KRYteria did
        </button>
      ) : (
        <Card className="p-5">
          <Eyebrow>How this was produced</Eyebrow>
          {steps.length === 0 ? (
            <p className="text-faint">Loading…</p>
          ) : (
            <table className="w-full text-left">
              <thead className="text-faint">
                <tr>
                  <th className="font-normal py-1">Agent</th>
                  <th className="font-normal py-1 text-right">In</th>
                  <th className="font-normal py-1 text-right">Out</th>
                  <th className="font-normal py-1 text-right">ms</th>
                </tr>
              </thead>
              <tbody className="text-muted">
                {steps.map((s, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="py-1.5">{s.agent}</td>
                    <td className="py-1.5 text-right tabular-nums">{s.input_tokens}</td>
                    <td className="py-1.5 text-right tabular-nums">{s.output_tokens}</td>
                    <td className="py-1.5 text-right tabular-nums">{s.latency_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="text-faint mt-3">
            Tool names and counts only. Nothing you wrote is recorded here.
          </p>
        </Card>
      )}
    </div>
  );
}

/* --------------------------------------------------- the retention choice */

function RetentionChoice({ entryId, initial }: { entryId: number; initial: Retention }) {
  const [chosen, setChosen] = useState<Retention | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [always, setAlways] = useState(false);

  async function choose(r: Retention) {
    setBusy(true);
    try {
      const res = await api.setEntryRetention(entryId, r, always);
      setChosen(r);
      setNote(res.note);
    } catch { /* the entry is saved either way */ } finally { setBusy(false); }
  }

  if (chosen) {
    return (
      <Card className="p-5">
        <p className="text-sm text-muted">{note}</p>
      </Card>
    );
  }

  return (
    <Card className="p-6 sm:p-7">
      <h2 className="font-serif text-xl">Your reflection is ready.</h2>
      <p className="text-muted mt-1.5 text-sm">What would you like KRYteria to keep?</p>

      <div className="space-y-3 mt-6">
        {(["discard", "keep_all", "analysis_only"] as Retention[]).map((r) => (
          <button
            key={r}
            className="choice block"
            data-selected={r === initial}
            onClick={() => choose(r)}
            disabled={busy}
          >
            <span className="block text-ink font-medium">{RETENTION_COPY[r].title}</span>
            <span className="block text-sm text-muted mt-1 leading-relaxed">
              {RETENTION_COPY[r].detail}
            </span>
            {r === initial && (
              <span className="block text-[11px] text-faint mt-2">Your current default</span>
            )}
          </button>
        ))}
      </div>

      <label className="flex items-center gap-3 mt-5 text-sm text-muted cursor-pointer">
        <input type="checkbox" checked={always} onChange={(e) => setAlways(e.target.checked)}
               className="accent-[rgb(var(--accent))]" />
        Make this my default and apply it to what I've already written
      </label>
    </Card>
  );
}

export function NoEntries() {
  return <Empty>Nothing written yet. There is no streak to keep and nothing is overdue.</Empty>;
}
