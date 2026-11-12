import { useEffect, useState } from "react";
import {
  api, type Criterion, type Person, type Profile, type ProfileCriterion, type Status,
  type Tier, type Relevance,
} from "../api";
import {
  Card, Empty, ErrorNote, Eyebrow, Pill, Section, Spinner, StatusPill, TierPill,
} from "../components/ui";
import { PersonPicker } from "../components/people";

/**
 * My KRYteria — the three-level model made visible.
 *
 *   the library   reusable standards, no tier, no profile
 *   profiles      configurations that select criteria and set THIS profile's tier
 *   assessment    one person, one profile, Pass / Unknown / Fail / Not applicable
 *
 * Nothing on this screen ranks a profile against another, and nothing judges a
 * criterion. "Soft hands" renders exactly like "Compatible relationship intentions".
 */
export default function Criteria() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [library, setLibrary] = useState<Criterion[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [rows, setRows] = useState<ProfileCriterion[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [personId, setPersonId] = useState<number | "">("");
  const [loading, setLoading] = useState(true);
  // Bumped whenever something changes this profile's criteria. `setSelected(same id)`
  // is not a state change, so it never re-ran the loader — which is why adding a
  // criterion worked on the server and did nothing visible on screen.
  const [rowsNonce, setRowsNonce] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [p, l, pe] = await Promise.all([api.profiles(), api.criteria(), api.people()]);
    setProfiles(p);
    setLibrary(l);
    setPeople(pe);
    if (selected === null && p.length) setSelected(p[0].id);
  }

  useEffect(() => { refresh().catch((e) => setError(String(e))).finally(() => setLoading(false)); }, []);

  useEffect(() => {
    // Clear first. Leaving the previous profile's rows in place while the next load is
    // in flight meant `already` briefly described the WRONG profile — so "Add from your
    // library" offered criteria that were already there, and the 409 died silently in a
    // try/finally with no catch. That is the "+ Soft hands does nothing" bug.
    setRows([]);
    if (selected === null) return;
    let cancelled = false;
    const load = personId === ""
      ? api.profileCriteria(selected)
      : api.assessments(selected, personId);
    load.then((r) => { if (!cancelled) setRows(r); })
      .catch((e) => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, [selected, personId, rowsNonce]);

  async function setRelevance(criterionId: number, relevance: Relevance) {
    if (selected === null) return;
    setRows((r) => r.map((x) => (x.criterion_id === criterionId ? { ...x, relevance } : x)));
    try { await api.setRelevance(selected, criterionId, relevance); }
    catch (e) { setError(String(e)); setRowsNonce((n) => n + 1); }
  }

  async function setTier(criterionId: number, tier: Tier) {
    if (selected === null) return;
    // Optimistic: the tier is the user's own setting, so it should feel immediate.
    setRows((r) => r.map((x) => (x.criterion_id === criterionId ? { ...x, tier } : x)));
    try { await api.setTier(selected, criterionId, tier); }
    catch (e) { setError(String(e)); }
  }

  async function setStatus(criterionId: number, status: Status) {
    if (selected === null || personId === "") return;
    setRows((r) => r.map((x) => (x.criterion_id === criterionId ? { ...x, assessment: status } : x)));
    try {
      await api.setAssessment({
        profile_id: selected, criterion_id: criterionId, person_id: personId, status,
      });
    } catch (e) { setError(String(e)); }
  }

  if (loading) return <Spinner label="Loading your criteria" />;

  const profile = profiles.find((p) => p.id === selected);

  return (
    <div>
      {error && <div className="mb-6"><ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote></div>}

      <Section
        title="My KRYteria"
        subtitle="Different things matter for different kinds of connection. Each profile is its own configuration — changing one never changes another."
        action={<Pill tone="accent">Saved profiles</Pill>}
      >
        {profiles.length === 0 ? (
          <Empty>No profiles yet. A profile is a set of standards for one kind of connection — a partner, a friend, a colleague. You can have as many as you like.</Empty>
        ) : (
          <div className="grid sm:grid-cols-2 gap-3">
            {profiles.map((p) => (
              <button
                key={p.id}
                className="choice"
                data-selected={p.id === selected}
                onClick={() => setSelected(p.id)}
              >
                <span className="flex items-start justify-between gap-3">
                  <span className="font-serif text-lg text-ink">{p.name}</span>
                  {p.context_label && <Pill>{p.context_label}</Pill>}
                </span>
                {p.objective && (
                  <span className="block text-sm text-muted mt-1">{p.objective}</span>
                )}
                <span className="block text-xs text-faint mt-2">
                  {p.criteria_count ?? 0} criteria
                </span>
              </button>
            ))}
          </div>
        )}
        <NewProfile onCreated={() => refresh()} />
      </Section>

      {profile && (
        <Section
          title={profile.name}
          subtitle="Each criterion carries its own importance here. The same standard can matter differently in another profile."
          action={
            <div className="w-56">
              <PersonPicker
                label="Assessing"
                people={people}
                value={personId}
                onChange={setPersonId}
                onAdded={(p) => setPeople((xs) => [...xs, p])}
            onRemoved={(id) => setPeople((xs) => xs.filter((x) => x.id !== id))}
              />
            </div>
          }
        >
          {rows.length === 0 ? (
            <Empty>Nothing added to this profile yet. Pick from your library below.</Empty>
          ) : (
            <Card>
              <ul className="divide-y divide-[rgb(var(--line))]">
                {rows.map((r) => (
                  <li key={r.criterion_id} className="px-5 py-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h3 className="text-ink">{r.value}</h3>
                        <p className="text-sm text-muted mt-0.5">{r.desired_behavior}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {r.relevance === "not_applicable"
                          ? <StatusPill status="not_applicable" />
                          : <TierPill tier={r.tier} />}
                      </div>
                    </div>

                    {r.relevance === "not_applicable" ? (
                      <div className="mt-3">
                        <p className="text-xs text-faint">
                          Not relevant to this profile. It stays in your library and is
                          untouched elsewhere.
                        </p>
                        <button
                          className="btn-quiet text-xs mt-2"
                          onClick={() => setRelevance(r.criterion_id, "relevant")}
                        >
                          Actually, this does matter here
                        </button>
                      </div>
                    ) : (
                      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
                        <TierChooser tier={r.tier} onChange={(t) => setTier(r.criterion_id, t)} />
                        {personId !== "" && (
                          <StatusChooser
                            status={r.assessment ?? "unknown"}
                            onChange={(s) => setStatus(r.criterion_id, s)}
                          />
                        )}
                        <button
                          className="text-xs text-faint hover:text-muted underline"
                          onClick={() => setRelevance(r.criterion_id, "not_applicable")}
                        >
                          Doesn't apply here
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {personId !== "" && (
            <p className="text-xs text-faint mt-3">
              Unknown is a real answer. Nothing here is a score, and KRYteria never sets
              a status for you.
            </p>
          )}

          <AddToProfile
            profileId={profile.id}
            library={library}
            already={new Set(rows.map((r) => r.criterion_id))}
            onAdded={() => { refresh(); setRowsNonce((n) => n + 1); }}
            onError={setError}
          />
        </Section>
      )}

      <Section
        title="Your library"
        subtitle="Every standard you've written down, in alphabetical order. Reusable across profiles, and never judged here."
      >
        {library.length === 0 ? (
          <Empty>Nothing yet. Whatever matters to you belongs here — it is yours to set.</Empty>
        ) : (
          <Card>
            <ul className="divide-y divide-[rgb(var(--line))]">
              {library.map((c) => (
                <li key={c.id} className="px-5 py-4">
                  <div className="flex items-baseline justify-between gap-4">
                    <h3 className="text-ink">{c.value}</h3>
                    {c.version > 1 && (
                      <span className="text-xs text-faint shrink-0">
                        revised {c.version - 1}×
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted mt-0.5">{c.desired_behavior}</p>
                  {c.why_it_matters && (
                    <p className="text-sm text-faint mt-1 italic">{c.why_it_matters}</p>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}
        <NewCriterion onCreated={() => refresh()} />
      </Section>
    </div>
  );
}

function TierChooser({ tier, onChange }: { tier: Tier; onChange: (t: Tier) => void }) {
  const tiers: Tier[] = ["mandatory", "preferred", "aspirational"];
  return (
    <div>
      <Eyebrow>How much it matters</Eyebrow>
      <div className="flex gap-1.5" role="radiogroup" aria-label="Importance">
        {tiers.map((t) => (
          <button
            key={t}
            role="radio"
            aria-checked={t === tier}
            onClick={() => onChange(t)}
            className={`pill border transition-colors ${
              t === tier
                ? "border-accent bg-accent/15 text-accent"
                : "border-line text-faint hover:text-muted"
            }`}
          >
            {t === "mandatory" ? "Mandatory" : t === "preferred" ? "Preferred" : "Aspirational"}
          </button>
        ))}
      </div>
    </div>
  );
}

function StatusChooser({ status, onChange }: { status: Status; onChange: (s: Status) => void }) {
  const options: Status[] = ["pass", "unknown", "fail"];
  const label: Record<string, string> = { pass: "Pass", unknown: "Unknown", fail: "Fail" };
  return (
    <div>
      <Eyebrow>What you know so far</Eyebrow>
      <div className="flex gap-1.5" role="radiogroup" aria-label="Assessment">
        {options.map((s) => (
          <button
            key={s}
            role="radio"
            aria-checked={s === status}
            onClick={() => onChange(s)}
            className={`pill border transition-colors ${
              s === status
                ? s === "pass" ? "border-support bg-support/15 text-support"
                : s === "fail" ? "border-contradict bg-contradict/15 text-contradict"
                : "border-muted bg-line/40 text-muted"
                : "border-line text-faint hover:text-muted"
            }`}
          >
            {label[s]}
          </button>
        ))}
      </div>
    </div>
  );
}

function NewCriterion({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [behavior, setBehavior] = useState("");
  const [why, setWhy] = useState("");
  const [busy, setBusy] = useState(false);

  if (!open) {
    return (
      <button className="btn-quiet mt-4" onClick={() => setOpen(true)}>
        Add a criterion
      </button>
    );
  }

  return (
    <Card className="p-6 mt-4">
      <h3 className="font-serif text-lg">Add a criterion</h3>
      <p className="text-sm text-muted mt-1">
        Whatever it is. KRYteria doesn't rank what matters to you.
      </p>
      <div className="space-y-4 mt-5">
        <div>
          <label htmlFor="c-value" className="eyebrow block">What you value</label>
          <input id="c-value" className="field mt-2" value={value}
                 onChange={(e) => setValue(e.target.value)} placeholder="Follow-through" />
        </div>
        <div>
          <label htmlFor="c-behavior" className="eyebrow block">What meeting it looks like</label>
          <input id="c-behavior" className="field mt-2" value={behavior}
                 onChange={(e) => setBehavior(e.target.value)}
                 placeholder="Does what they said they would do" />
        </div>
        <div>
          <label htmlFor="c-why" className="eyebrow block">
            Why it matters <span className="text-faint normal-case tracking-normal">(optional)</span>
          </label>
          <input id="c-why" className="field mt-2" value={why}
                 onChange={(e) => setWhy(e.target.value)} />
        </div>
      </div>
      <div className="flex gap-3 mt-5">
        <button
          className="btn-accent"
          disabled={busy || !value.trim() || !behavior.trim()}
          onClick={async () => {
            setBusy(true);
            try {
              await api.createCriterion({
                value, desired_behavior: behavior, why_it_matters: why || null,
              });
              setValue(""); setBehavior(""); setWhy(""); setOpen(false); onCreated();
            } finally { setBusy(false); }
          }}
        >
          Add to library
        </button>
        <button className="btn-quiet" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </Card>
  );
}

function NewProfile({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button className="btn-quiet mt-4" onClick={() => setOpen(true)}>
        New profile
      </button>
    );
  }

  return (
    <Card className="p-6 mt-4">
      <h3 className="font-serif text-lg">New KRYteria profile</h3>
      <p className="text-sm text-muted mt-1">
        Name it whatever you call it. No profile ranks above another.
      </p>
      <div className="space-y-4 mt-5">
        <div>
          <label htmlFor="p-name" className="eyebrow block">Name</label>
          <input id="p-name" className="field mt-2" value={name}
                 onChange={(e) => setName(e.target.value)} placeholder="Boyfriend KRYteria" />
        </div>
        <div>
          <label htmlFor="p-obj" className="eyebrow block">
            What you're looking for <span className="text-faint normal-case tracking-normal">(optional)</span>
          </label>
          <input id="p-obj" className="field mt-2" value={objective}
                 onChange={(e) => setObjective(e.target.value)} placeholder="Exclusive dating" />
        </div>
        <div>
          <label htmlFor="p-label" className="eyebrow block">
            Short label <span className="text-faint normal-case tracking-normal">(optional)</span>
          </label>
          <input id="p-label" className="field mt-2" value={label}
                 onChange={(e) => setLabel(e.target.value)} placeholder="Dating" />
        </div>
      </div>
      {error && <div className="mt-4"><ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote></div>}
      <div className="flex gap-3 mt-5">
        <button
          className="btn-accent"
          disabled={busy || !name.trim()}
          onClick={async () => {
            setBusy(true); setError(null);
            try {
              await api.createProfile({
                name, objective: objective || null, context_label: label || null,
              });
              setName(""); setObjective(""); setLabel(""); setOpen(false); onCreated();
            } catch (e) {
              setError(e instanceof Error ? e.message : String(e));
            } finally { setBusy(false); }
          }}
        >
          Create profile
        </button>
        <button className="btn-quiet" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </Card>
  );
}

function AddToProfile({ profileId, library, already, onAdded, onError }: {
  profileId: number; library: Criterion[]; already: Set<number>;
  onAdded: () => void; onError: (m: string) => void;
}) {
  const available = library.filter((c) => !already.has(c.id));
  const [busy, setBusy] = useState<number | null>(null);
  if (available.length === 0) return null;

  return (
    <div className="mt-5">
      <Eyebrow>Add from your library — alphabetical</Eyebrow>
      <div className="flex flex-wrap gap-2">
        {available.map((c) => (
          <button
            key={c.id}
            className="pill border border-line text-muted hover:border-accent hover:text-accent transition-colors"
            disabled={busy === c.id}
            onClick={async () => {
              setBusy(c.id);
              // A silent catch here is how "+ does nothing" happened. Say it instead.
              try { await api.addToProfile(profileId, { criterion_id: c.id }); onAdded(); }
              catch (e) { onError(e instanceof Error ? e.message : String(e)); }
              finally { setBusy(null); }
            }}
          >
            + {c.value}
          </button>
        ))}
      </div>
    </div>
  );
}
