import { useEffect, useState } from "react";
import { api, type Person } from "../api";
import { awaitingChoice, placeholderFor } from "../choice";

/**
 * Choosing a person, and adding one without leaving the page.
 *
 * People exist only as aliases the user chose — there is no field for a real name, and
 * the helper text says so, because somebody typing a partner's full name into a private
 * journal deserves to be told they don't have to.
 */
export function PersonPicker({ people, value, onChange, onAdded, onRemoved,
                               label = "About whom" }: {
  people: Person[];
  value: number | "";
  onChange: (id: number | "") => void;
  onAdded: (p: Person) => void;
  /** Omit to hide the remove control — useful where removal would be surprising. */
  onRemoved?: (id: number) => void;
  label?: string;
}) {
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Person | null>(null);
  const [alias, setAlias] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (!alias.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const person = await api.createPerson(alias.trim(), role.trim() || undefined);
      onAdded(person);
      onChange(person.id);
      setAlias("");
      setRole("");
      setAdding(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (adding) {
    return (
      <div>
        <span className="eyebrow block">Who is this?</span>
        <input
          className="field mt-2"
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          placeholder="A name only you would recognise"
          autoFocus
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
        />
        <input
          className="field mt-2"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          placeholder="How you'd describe them (optional)"
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
        />
        <p className="text-xs text-faint mt-2">
          An alias is enough — KRYteria never needs anybody's real name, and nobody can
          ever learn they appear here.
        </p>
        {error && <p className="text-xs text-contradict mt-2">{error}</p>}
        <div className="flex gap-2 mt-3">
          <button className="btn-accent text-xs px-4 py-1.5" disabled={busy || !alias.trim()}
                  onClick={add}>
            Add
          </button>
          <button className="btn-quiet text-xs px-4 py-1.5"
                  onClick={() => { setAdding(false); setError(null); }}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (removing) {
    return (
      <RemovePerson
        person={removing}
        onCancel={() => setRemoving(null)}
        onRemoved={() => {
          onRemoved?.(removing.id);
          if (value === removing.id) onChange("");
          setRemoving(null);
        }}
      />
    );
  }

  const selected = people.find((p) => p.id === value);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="eyebrow">{label}</span>
        <span className="flex gap-3">
          {selected && onRemoved && (
            <button
              className="text-[11px] text-faint hover:text-contradict transition-colors"
              onClick={() => setRemoving(selected)}
            >
              Remove {selected.alias}
            </button>
          )}
          <button
            className="text-[11px] text-accent hover:underline"
            onClick={() => setAdding(true)}
          >
            + Add someone
          </button>
        </span>
      </div>
      <select
        className="field mt-2"
        value={value}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
      >
        <option value="">
          {placeholderFor(people.length, "Who are we talking about? —",
                          "Nobody in particular")}
        </option>
        {people.map((p) => (
          <option key={p.id} value={p.id}>
            {p.alias}{p.role_label ? ` — ${p.role_label}` : ""}
          </option>
        ))}
      </select>
      {awaitingChoice(people.length, value) && (
        <p className="text-xs text-faint mt-2">
          Choosing someone lets KRYteria notice what recurs with them. It won't work it
          out from your writing — too many people share a name, and attaching evidence
          to the wrong person would quietly corrupt the record.
        </p>
      )}
      {people.length === 0 && (
        <p className="text-xs text-faint mt-2">
          Add someone to start tracking what recurs with them over time.
        </p>
      )}
    </div>
  );
}

/**
 * Removing somebody, with what it destroys shown first.
 *
 * Two different acts, deliberately separated: taking a name off the list, and erasing
 * that they were ever here. Somebody may want either, and conflating them would mean a
 * tidy-up silently destroys a month of journal.
 */
function RemovePerson({ person, onCancel, onRemoved }: {
  person: Person;
  onCancel: () => void;
  onRemoved: () => void;
}) {
  const [footprint, setFootprint] = useState<{ entries: number; assessments: number } | null>(null);
  const [alsoEntries, setAlsoEntries] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.personFootprint(person.id).then(setFootprint).catch(() => {});
  }, [person.id]);

  return (
    <div className="border border-contradict/40 rounded-xl p-4">
      <p className="text-sm text-ink">Remove {person.alias}?</p>

      {footprint === null ? (
        <p className="text-xs text-faint mt-2">Checking what this affects…</p>
      ) : (
        <ul className="text-xs text-muted mt-2 space-y-1">
          <li>
            {footprint.assessments === 0
              ? "No assessments to remove."
              : `${footprint.assessments} assessment${footprint.assessments === 1 ? "" : "s"} will be removed — a Pass or Fail means nothing without them.`}
          </li>
          <li>
            {footprint.entries === 0
              ? "You haven't written anything about them."
              : alsoEntries
                ? `${footprint.entries} ${footprint.entries === 1 ? "entry" : "entries"} will be deleted too.`
                : `${footprint.entries} ${footprint.entries === 1 ? "entry" : "entries"} will stay in your journal, no longer attached to anybody.`}
          </li>
        </ul>
      )}

      {(footprint?.entries ?? 0) > 0 && (
        <label className="flex items-start gap-2.5 mt-3 text-xs text-muted cursor-pointer">
          <input type="checkbox" checked={alsoEntries}
                 onChange={(e) => setAlsoEntries(e.target.checked)}
                 className="mt-0.5 accent-[rgb(var(--accent))]" />
          Also delete what I wrote about them
        </label>
      )}

      <div className="flex gap-2 mt-4">
        <button
          className="btn text-xs px-4 py-1.5 border border-contradict text-contradict hover:bg-contradict hover:text-ground"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try { await api.deletePerson(person.id, alsoEntries); onRemoved(); }
            finally { setBusy(false); }
          }}
        >
          {alsoEntries ? "Remove and delete" : "Remove"}
        </button>
        <button className="btn-quiet text-xs px-4 py-1.5" onClick={onCancel}>Cancel</button>
      </div>
      <p className="text-xs text-faint mt-3">This cannot be undone.</p>
    </div>
  );
}
