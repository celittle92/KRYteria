import { useEffect, useState } from "react";
import { api, type Person, type Progress } from "../api";
import { PersonPicker } from "../components/people";
import { Card, DECISION_COPY, Empty, Eyebrow, Section, Spinner, StrengthPill } from "../components/ui";

/**
 * My Progress — the longitudinal view, and the screen most at risk of becoming a
 * scoreboard.
 *
 * It shows: criteria against observed experience, recurring unmet needs, decisions
 * repeatedly postponed, how stated priorities have changed, and the actions chosen.
 *
 * It does NOT show: any score, any percentage, any streak, any trend line implying one,
 * or a count of people dated or relationships ended. Progress here means the user's own
 * thinking, not their throughput.
 */
export default function ProgressScreen() {
  const [data, setData] = useState<Progress | null>(null);
  const [loading, setLoading] = useState(true);
  const [people, setPeople] = useState<Person[]>([]);
  const [themePerson, setThemePerson] = useState<number | "">("");
  const [themes, setThemes] = useState<Progress["themes"]>([]);

  useEffect(() => {
    api.progress().then((d) => { setData(d); setThemes(d.themes ?? []); })
      .catch(() => {}).finally(() => setLoading(false));
    api.people().then(setPeople).catch(() => {});
  }, []);

  // Christine, 2026-11-12: "it would be helpful to be able to filter on different
  // partners to see if you have different patterns with different people — i.e. you let
  // a hottie get away with a lot more than someone you're attracted to but not as
  // much."
  //
  // That is the brand's own fourth question — *am I making exceptions for someone that
  // I wouldn't make for anyone else?* — made answerable instead of rhetorical. Counts
  // only: it shows what differs and never says which person is being treated correctly.
  useEffect(() => {
    api.themesFor(themePerson === "" ? null : themePerson)
      .then((r) => setThemes(r.themes.filter((x) => x.entries > 0)))
      .catch(() => {});
  }, [themePerson]);

  if (loading) return <Spinner label="Looking back over your record" />;
  if (!data) return <Empty>Nothing to show yet.</Empty>;

  const decisions = Object.entries(data.decisions_by_choice);
  const nothing = data.entries === 0 && data.active_criteria === 0;

  if (nothing) {
    return (
      <Section title="My Progress" subtitle="How your own thinking has moved.">
        <Empty>
          This fills in as you write. There's nothing to catch up on and no streak to
          keep — a week with nothing in it is not a gap.
        </Empty>
      </Section>
    );
  }

  return (
    <div>
      <Section title="My Progress" subtitle="Your criteria set against what you've actually recorded, and what you chose to do about it.">
        <div className="grid sm:grid-cols-3 gap-4">
          <Count label="Standards you've written" value={data.active_criteria} />
          <Count label="Experiences recorded" value={data.entries} />
          <Count
            label="Open questions"
            value={data.unanswered_questions.length}
            note={data.unanswered_questions.length === 0 ? "Nothing waiting" : undefined}
          />
        </div>
        <p className="text-xs text-faint mt-3">
          Counts, not scores. Nothing here rates you or anybody else.
        </p>
      </Section>

      {data.repeatedly_postponed.length > 0 && (
        <Section
          title="Decisions you've put off"
          subtitle="Recorded without judgment. Giving something more time is a decision, and sometimes the right one."
        >
          <Card>
            <ul className="divide-y divide-[rgb(var(--line))]">
              {data.repeatedly_postponed.map((r) => (
                <li key={r.criterion_id} className="px-5 py-4 flex items-baseline justify-between gap-4">
                  <span className="text-ink">{r.value}</span>
                  <span className="text-sm text-muted">
                    {r.count} {r.count === 1 ? "time" : "times"}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </Section>
      )}

      {data.changed_priorities.length > 0 && (
        <Section
          title="How your standards have changed"
          subtitle="Every version is kept. Seeing a standard soften — or harden — is often the most useful thing on this page."
        >
          <div className="space-y-4">
            {data.changed_priorities.map((c) => (
              <Card key={c.criterion_id} className="p-6">
                <h3 className="text-ink">{c.value}</h3>
                <ol className="mt-4 space-y-4">
                  {c.versions.map((v) => (
                    <li key={v.id} className="flex gap-4">
                      <span className="text-xs text-faint tabular-nums shrink-0 w-24">
                        {v.created_at.slice(0, 10)}
                      </span>
                      <div>
                        <p className="text-sm text-muted">{v.desired_behavior}</p>
                        {v.revision_note && (
                          <p className="text-sm text-faint italic mt-1">
                            "{v.revision_note}"
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </Card>
            ))}
          </div>
        </Section>
      )}

      {((themes ?? []).length > 0 || themePerson !== "") && (
        <Section
          title="What you keep coming back to"
          subtitle="The subjects your entries have been about. Recognized as you wrote — you never had to label anything."
          action={
            people.length > 1 ? (
              <div className="w-56">
                <PersonPicker
                  label="For"
                  people={people}
                  value={themePerson}
                  onChange={setThemePerson}
                  onAdded={(p) => setPeople((xs) => [...xs, p])}
                  onRemoved={(id) => setPeople((xs) => xs.filter((x) => x.id !== id))}
                />
              </div>
            ) : undefined
          }
        >
          <Card>
            <ul className="divide-y divide-[rgb(var(--line))]">
              {(themes ?? []).map((t) => (
                <li key={t.theme_id} className="px-5 py-3 flex items-baseline justify-between gap-4">
                  <span className="text-ink text-sm flex-1">{t.label}</span>
                  <span className="text-muted text-sm tabular-nums">
                    {t.entries} {t.entries === 1 ? "entry" : "entries"}
                  </span>
                  {t.last_seen && (
                    <span className="text-faint text-xs tabular-nums w-24 text-right">
                      last {t.last_seen}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </Card>
          {/* Counts and dates only. A theme says a subject came up — never that
              anybody did well or badly at it, and never a score. */}
          {(themes ?? []).length === 0 && (
            <Empty>Nothing recorded about this person yet.</Empty>
          )}
          <p className="text-xs text-faint mt-3 max-w-reading leading-relaxed">
            A count, not a verdict. That something comes up often says it matters to
            you, not that it is going wrong — and you may not have made it a criterion
            yet.
            {people.length > 1 && (
              <> Switching between people is worth doing: what you write about with one
              person and not another is often the more interesting question.</>
            )}
          </p>
        </Section>
      )}

      {data.open_patterns.length > 0 && (
        <Section title="What recurs" subtitle="Findings still open, each resting on entries you can inspect.">
          <Card>
            <ul className="divide-y divide-[rgb(var(--line))]">
              {data.open_patterns.map((p) => (
                <li key={p.id} className="px-5 py-4 flex items-start justify-between gap-4">
                  <span className="text-muted text-sm flex-1">{p.statement}</span>
                  <StrengthPill strength={p.evidence_strength} />
                </li>
              ))}
            </ul>
          </Card>
        </Section>
      )}

      {decisions.length > 0 && (
        <Section title="What you chose" subtitle="Every decision you've recorded, including the ones to wait.">
          <Card className="p-6">
            <ul className="space-y-2.5">
              {decisions
                .sort((a, b) => b[1] - a[1])
                .map(([choice, count]) => (
                  <li key={choice} className="flex items-baseline justify-between gap-4">
                    <span className="text-muted text-sm">
                      {DECISION_COPY[choice] ?? choice}
                    </span>
                    <span className="text-sm text-faint tabular-nums">{count}</span>
                  </li>
                ))}
            </ul>
          </Card>
        </Section>
      )}

      {data.recent_entries.length > 0 && (
        <Section title="Recently" subtitle="Entries whose original you chose to erase show as a date with nothing in them. That is working as intended.">
          <Card>
            <ul className="divide-y divide-[rgb(var(--line))]">
              {data.recent_entries.map((e) => (
                <li key={e.id} className="px-5 py-4">
                  <div className="flex items-baseline gap-4">
                    <span className="text-xs text-faint tabular-nums shrink-0 w-24">
                      {e.occurred_on}
                    </span>
                    <p className="text-sm text-muted flex-1">
                      {e.body ?? e.what_happened ?? (
                        <span className="text-faint italic">
                          Original erased — the analysis was kept
                        </span>
                      )}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </Section>
      )}
    </div>
  );
}

function Count({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <Card className="p-5">
      <Eyebrow>{label}</Eyebrow>
      <p className="font-serif text-3xl tabular-nums">{value}</p>
      {note && <p className="text-xs text-faint mt-1">{note}</p>}
    </Card>
  );
}
