import { useEffect, useState } from "react";
import {
  api, type ChecklistItem, type ChecklistState, type Person, type Profile,
  type ProfileCriterion,
} from "../api";
import { Card, ErrorNote, Eyebrow, Section, Spinner } from "../components/ui";
import { PersonPicker } from "../components/people";
import { awaitingChoice, placeholderFor, soleOrNone } from "../choice";

/**
 * Checklist Mode — the other direction through the same intelligence layer.
 *
 * The Brain Dump goes experiences → criteria. This goes criteria → behaviors: *"I care
 * about emotional maturity"* becomes a list of things you might actually observe. For
 * people who do not want to write paragraphs after every date, and for anyone who does
 * not yet know what to look for.
 *
 * THE RULE THIS SCREEN EXISTS TO HOLD, stated in the interface and enforced in the
 * store: **ticking an item records an observation. It does not establish that the
 * criterion passes.** Nothing here moves a status. That is why the counts below are
 * counts and never a score, and why "not observed" is kept distinct from "no
 * opportunity to observe" — someone who has never disagreed with a person cannot
 * conclude that person handles disagreement well.
 */

// The two negative states are the ones that carry the weight, and their first labels
// — "No chance to see" and "Didn't see it" — did not say how they differed. They are
// different in the way that matters most: one is no evidence at all, the other is
// evidence. If plans never came up, nothing has been learned about how he handles
// plans. If plans came up and he said nothing about his schedule, something has.
//
// The labels now carry that on their own, instead of relying on a hint the eye skips.
const STATES: { value: ChecklistState; label: string; hint: string }[] = [
  {
    value: "observed", label: "Yes, saw this",
    hint: "It happened, at least once.",
  },
  {
    value: "contradicted", label: "Saw the opposite",
    hint: "The reverse happened.",
  },
  {
    value: "no_opportunity", label: "Hasn't come up",
    hint: "The situation has not arisen, so there is nothing to have seen. This is not "
        + "evidence of absence, and it is not held against anyone.",
  },
  {
    value: "not_observed", label: "Came up, didn't happen",
    hint: "The situation did arise and this did not happen. That is a real observation, "
        + "unlike 'hasn't come up'.",
  },
];

export default function Checklist() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [profileId, setProfileId] = useState<number | "">("");
  const [personId, setPersonId] = useState<number | "">("");
  const [criteria, setCriteria] = useState<ProfileCriterion[]>([]);
  const [criterionId, setCriterionId] = useState<number | "">("");
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [clarification, setClarification] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState<number | null>(null);

  useEffect(() => {
    api.profiles().then((ps) => { setProfiles(ps); setProfileId(soleOrNone(ps)); })
      .catch(() => {});
    api.people().then((ps) => { setPeople(ps); setPersonId(soleOrNone(ps)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setCriterionId(""); setItems([]); setClarification(null);
    if (profileId === "") { setCriteria([]); return; }
    api.profileCriteria(profileId)
      .then((rows) => setCriteria(rows.filter((r) => r.relevance === "relevant")))
      .catch(() => setCriteria([]));
  }, [profileId]);

  useEffect(() => {
    if (criterionId === "") { setItems([]); return; }
    setLoading(true);
    setClarification(null);
    api.checklist(criterionId, {
      profile_id: profileId === "" ? undefined : profileId,
      person_id: personId === "" ? undefined : personId,
    })
      .then(setItems)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [criterionId, profileId, personId]);

  async function generate() {
    if (criterionId === "") return;
    setGenerating(true); setError(null);
    try {
      const r = await api.generateChecklist(
        criterionId, profileId === "" ? undefined : profileId);
      setItems(r.indicators);
      setClarification(r.clarification);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function observe(item: ChecklistItem, state: ChecklistState) {
    setError(null);
    try {
      await api.observeIndicator(item.id, {
        person_id: personId === "" ? null : personId, state,
      });
      setJustSaved(item.id);
      setTimeout(() => setJustSaved((x) => (x === item.id ? null : x)), 2500);
      if (personId !== "") {
        setItems(await api.checklist(criterionId as number, {
          profile_id: profileId === "" ? undefined : profileId,
          person_id: personId,
        }));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const criterionName =
    criteria.find((c) => c.criterion_id === criterionId)?.value ?? "";

  return (
    <div className="space-y-10">
      <Section
        title="Checklist"
        subtitle="Turn a standard into things you could actually notice. Tapping one records an observation — it never decides whether the criterion is met."
      >
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <span className="eyebrow block">Which KRYteria</span>
            <select
              className="field mt-2"
              value={profileId}
              onChange={(e) =>
                setProfileId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">
                {placeholderFor(profiles.length, "Which one? —", "Choose a profile")}
              </option>
              {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            {awaitingChoice(profiles.length, profileId) && (
              <p className="text-xs text-faint mt-2">
                Indicators are per profile — what shows consideration in one may not be
                the point in another.
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

        {profileId !== "" && (
          <div className="mt-5">
            <span className="eyebrow block">Which standard</span>
            <select
              className="field mt-2"
              value={criterionId}
              onChange={(e) =>
                setCriterionId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">Choose one —</option>
              {criteria.map((c) => (
                <option key={c.criterion_id} value={c.criterion_id}>
                  {c.value} · {c.tier}
                </option>
              ))}
            </select>
          </div>
        )}
      </Section>

      {error && <ErrorNote>{error}</ErrorNote>}

      {criterionId !== "" && (
        <Section
          title={criterionName}
          subtitle="Suggestions, not a definition. Yours is the only definition that counts — reject anything that isn't what you meant."
        >
          {loading && <Spinner label="Loading what to look for…" />}

          {!loading && items.length === 0 && (
            <Card>
              <div className="px-5 py-6">
                <p className="text-muted text-sm max-w-reading leading-relaxed">
                  Nothing here yet. KRYteria can suggest behaviors that might show this
                  standard — or contradict it — based on what you wrote about why it
                  matters.
                </p>
                <button className="btn mt-4" onClick={generate} disabled={generating}>
                  {generating ? "Thinking…" : "Suggest things to look for"}
                </button>
                <p className="text-xs text-faint mt-3 max-w-reading leading-relaxed">
                  These are starting points to edit or ignore, not a universal
                  definition of what this standard means.
                </p>
              </div>
            </Card>
          )}

          {clarification && (
            <p className="voice text-ink mb-4 max-w-reading">{clarification}</p>
          )}

          {items.length > 0 && (
            <>
              <Card>
                <ul className="divide-y divide-[rgb(var(--line))]">
                  {items.map((item) => (
                    <li key={item.id} className="px-5 py-4">
                      <div className="flex items-start justify-between gap-4">
                        <span className="text-ink text-sm flex-1">
                          {item.text}
                          {item.polarity === "contradicts" && (
                            <span className="text-clay text-xs ml-2">
                              counts against
                            </span>
                          )}
                        </span>
                        {personId !== "" && (
                          <span className="text-faint text-xs tabular-nums whitespace-nowrap">
                            {item.times_observed ?? 0} seen ·{" "}
                            {item.times_contradicted ?? 0} opposite
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap gap-2 mt-3">
                        {STATES.map((s) => (
                          <button
                            key={s.value}
                            className="btn-quiet text-xs"
                            title={s.hint}
                            onClick={() => observe(item, s.value)}
                          >
                            {s.label}
                          </button>
                        ))}
                        {justSaved === item.id && (
                          <span className="text-accent text-xs self-center">
                            Recorded — this hasn't changed any status.
                          </span>
                        )}
                      </div>

                      {item.research_ref && (
                        <p className="text-faint text-xs mt-2">
                          Suggested from research: {item.research_ref}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>

              <div className="mt-4 max-w-reading space-y-2">
                <p className="text-xs text-faint leading-relaxed">
                  <strong className="text-muted">Ticking is not deciding.</strong>{" "}
                  Everything here is an observation. Whether this standard is met stays
                  yours to set, on the assessment screen, and KRYteria will not move it
                  for you.
                </p>
                <p className="text-xs text-faint leading-relaxed">
                  <strong className="text-muted">"Hasn't come up" is not a fail.</strong>{" "}
                  If you have never disagreed with someone, you cannot conclude they
                  handle disagreement badly — or well. That is different from "came up,
                  didn't happen", which is a real observation. The two are kept apart on
                  purpose, and nothing here is ever counted against anyone for being
                  unobserved.
                </p>
              </div>
            </>
          )}
        </Section>
      )}

      {criterionId === "" && profileId !== "" && (
        <p className="text-sm text-faint max-w-reading">
          <Eyebrow>Why this exists</Eyebrow>
          Not everybody wants to write a paragraph after every date. This is the same
          reasoning as the Brain Dump, run the other way round — from what you said
          matters, toward what you could actually watch for.
        </p>
      )}
    </div>
  );
}
