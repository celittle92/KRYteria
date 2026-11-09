import { useEffect, useState } from "react";
import { api, type Progress } from "../api";
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

  useEffect(() => {
    api.progress().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

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
          subtitle="Recorded without judgement. Giving something more time is a decision, and sometimes the right one."
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
