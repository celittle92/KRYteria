import { useEffect, useState } from "react";
import { api, type Pattern } from "../api";
import { Card, Empty, Eyebrow, Section, Spinner, StrengthPill } from "../components/ui";

/**
 * Findings, with the entries they rest on — and the entries that cut against them.
 *
 * Counter-evidence is displayed at the same visual weight as supporting evidence, not
 * folded into a footnote. A screen that only shows agreement is building a case.
 *
 * "Insufficient evidence" findings are listed, not hidden. "I don't have enough to say"
 * is a result somebody is entitled to see.
 */
export default function Patterns() {
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.patterns().then(setPatterns).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner label="Looking at what you've recorded" />;

  const settled = patterns.filter((p) => p.evidence_strength !== "insufficient");
  const unsettled = patterns.filter((p) => p.evidence_strength === "insufficient");

  return (
    <div>
      <Section
        title="Patterns"
        subtitle="What KRYteria has concluded, and why. Every finding names the entries it rests on, so you can check it yourself. Nothing here asks anything of you — questions live in Reflection."
      >
        {settled.length === 0 ? (
          <Empty>
            Nothing yet that KRYteria would call a pattern. That is not a gap to fill —
            it usually means there simply isn't enough recorded to say anything honest.
          </Empty>
        ) : (
          <div className="space-y-4">
            {settled.map((p) => <PatternCard key={p.id} pattern={p} />)}
          </div>
        )}
      </Section>

      {unsettled.length > 0 && (
        <Section
          title="Not settled"
          subtitle="Things KRYteria noticed but cannot responsibly call a pattern yet. Shown because the gap is itself worth knowing about."
        >
          <div className="space-y-4">
            {unsettled.map((p) => <PatternCard key={p.id} pattern={p} />)}
          </div>
        </Section>
      )}
    </div>
  );
}

function PatternCard({ pattern }: { pattern: Pattern }) {
  const [open, setOpen] = useState(false);

  return (
    <Card className="p-6">
      {/* Stacks on a phone. Side by side, the no-wrap strength pill takes ~150px of a
          375px screen and the finding renders two words per line — a tall thin column
          that is the first thing somebody sees after "See it working". Found by looking
          at the real screen at 375px rather than at the laptop it was written on. */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between
                      gap-2 sm:gap-4">
        <p className="voice text-lg leading-relaxed flex-1">{pattern.statement}</p>
        <StrengthPill strength={pattern.evidence_strength} />
      </div>

      <p className="text-sm text-muted mt-3">
        {pattern.support_count === 0
          ? "No entries support this."
          : `${pattern.support_count} ${pattern.support_count === 1 ? "entry supports" : "entries support"} this`}
        {pattern.contra_count > 0 && (
          <>
            {" · "}
            <span className="text-contradict">
              {pattern.contra_count} {pattern.contra_count === 1 ? "cuts" : "cut"} against it
            </span>
          </>
        )}
      </p>

      {pattern.gap_note && (
        <p className="text-sm text-muted mt-3 leading-relaxed">{pattern.gap_note}</p>
      )}

      {pattern.alternatives.length > 0 && (
        <div className="mt-5">
          <Eyebrow>Other explanations</Eyebrow>
          <ul className="space-y-1.5">
            {pattern.alternatives.map((a, i) => (
              <li key={i} className="text-sm text-muted">{a}</li>
            ))}
          </ul>
        </div>
      )}

      {pattern.uncertainties.length > 0 && (
        <div className="mt-5">
          <Eyebrow>Still unknown</Eyebrow>
          <ul className="space-y-1.5">
            {pattern.uncertainties.map((u, i) => (
              <li key={i} className="text-sm text-muted">{u}</li>
            ))}
          </ul>
        </div>
      )}

      <button
        className="text-sm text-accent hover:underline mt-5"
        onClick={() => setOpen(!open)}
      >
        {open ? "Hide the evidence" : "Show me the entries"}
      </button>

      {open && (
        <div className="mt-5 grid sm:grid-cols-2 gap-6">
          <div>
            <Eyebrow>What supports it</Eyebrow>
            {pattern.evidence.length === 0 ? (
              <p className="text-sm text-faint">Nothing.</p>
            ) : (
              <ul className="space-y-3">
                {pattern.evidence.map((e, i) => (
                  <li key={i} className="text-sm">
                    <span className="text-faint tabular-nums">{e.occurred_on}</span>
                    <p className="text-muted mt-0.5">{e.excerpt ?? "(original erased)"}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <Eyebrow>What cuts against it</Eyebrow>
            {pattern.counter_evidence.length === 0 ? (
              <p className="text-sm text-faint">Nothing recorded yet.</p>
            ) : (
              <ul className="space-y-3">
                {pattern.counter_evidence.map((e, i) => (
                  <li key={i} className="text-sm">
                    <span className="text-faint tabular-nums">{e.occurred_on}</span>
                    <p className="text-muted mt-0.5">{e.excerpt ?? "(original erased)"}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
