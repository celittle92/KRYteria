import { useEffect, useState } from "react";
import { api, type Entry, type Observation } from "../api";
import {
  Card, Empty, Eyebrow, ErrorNote, Quoted, RelationPill, Section, Spinner,
} from "../components/ui";

/**
 * Everything written, and what KRYteria made of it.
 *
 * This screen was missing and its absence was worse than it looked. The analysis has
 * always been produced, stored and traceable — observations separated by kind, evidence
 * mapped to criteria with a relation, questions about the claims — but it was only ever
 * visible in the moment just after writing an entry. Close the tab and the work was
 * unreachable except through the API.
 *
 * For a product whose whole argument is that a record is worth more than a conversation,
 * being unable to reread the record was the wrong gap to have.
 *
 * What it must not do:
 *
 *   - **Never blend what was reported with what was concluded.** Observations are grouped
 *     by kind and labelled, because that distinction is the product, not a detail of it.
 *   - **Never present an inference as a fact.** An inferred observation carries the hedge
 *     the agent wrote with it, which is an invitation to correct it.
 *   - **Never hide the ambiguous mapping.** `complicating` is shown at the same weight as
 *     supporting and contradicting; collapsing it would force a verdict the evidence does
 *     not support.
 */

const KIND_COPY: Record<Observation["kind"], { title: string; detail: string }> = {
  reported_event: {
    title: "What happened",
    detail: "Events as you described them.",
  },
  interpretation: {
    title: "What you concluded",
    detail: "Your readings of those events — yours, not KRYteria's.",
  },
  emotional_reaction: {
    title: "How it affected you",
    detail: "What you felt, which is evidence about you rather than about them.",
  },
  missing_information: {
    title: "What is missing",
    detail: "Things the entry does not settle either way.",
  },
  uncertainty: {
    title: "What is unresolved",
    detail: "Questions you left open.",
  },
};

const KIND_ORDER: Observation["kind"][] = [
  "reported_event", "interpretation", "emotional_reaction",
  "missing_information", "uncertainty",
];

export default function Journal() {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Awaited<ReturnType<typeof api.entry>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.entries().then(setEntries).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (openId === null) { setDetail(null); return; }
    setLoading(true);
    setDetail(null);
    api.entry(openId)
      .then(setDetail)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [openId]);

  if (entries === null && !error) return <Spinner label="Loading your journal…" />;

  return (
    <Section
      title="Journal"
      subtitle="Everything you have written, and what KRYteria made of it."
    >
      {error && <ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote>}

      {entries && entries.length === 0 ? (
        <Empty>Nothing written yet. The Brain Dump is the front door.</Empty>
      ) : (
        <ul className="space-y-3">
          {entries?.map((e) => {
            const open = openId === e.id;
            const erased = e.original_erased_at !== null;
            return (
              <li key={e.id}>
                <Card className="overflow-hidden">
                  <button
                    className="w-full text-left p-5"
                    onClick={() => setOpenId(open ? null : e.id)}
                    aria-expanded={open}
                  >
                    <span className="flex items-baseline justify-between gap-4">
                      <Eyebrow>{e.occurred_on}</Eyebrow>
                      <span className="text-xs text-faint">
                        {e.people?.length ? e.people.join(", ") : "no one named"}
                      </span>
                    </span>
                    <span className="block mt-2 leading-relaxed">
                      {erased ? (
                        <em className="text-muted">
                          You asked for this to be erased. The analysis below survives;
                          what you wrote does not.
                        </em>
                      ) : (
                        <>
                          {(e.body ?? e.what_happened ?? "").slice(0, 190)}
                          {(e.body ?? e.what_happened ?? "").length > 190 && "…"}
                        </>
                      )}
                    </span>
                    <span className="block text-xs text-muted mt-3">
                      {open ? "Hide what KRYteria made of it" : "Show what KRYteria made of it"}
                    </span>
                  </button>

                  {open && (
                    <div className="border-t border-hair p-5 space-y-7">
                      {loading && <Spinner label="Opening…" />}

                      {detail && !erased && (
                        <Quoted label="What you wrote">{detail.body}</Quoted>
                      )}

                      {detail && detail.observations.length === 0 && (
                        <Empty>
                          This entry has not been analysed. Saving without analysis keeps
                          what you wrote and asks nothing of a model.
                        </Empty>
                      )}

                      {detail && KIND_ORDER.map((kind) => {
                        const rows = detail.observations.filter((o) => o.kind === kind);
                        if (!rows.length) return null;
                        return (
                          <div key={kind}>
                            <Eyebrow>{KIND_COPY[kind].title}</Eyebrow>
                            <p className="text-xs text-faint mt-1">
                              {KIND_COPY[kind].detail}
                            </p>
                            <ul className="mt-3 space-y-2.5">
                              {rows.map((o) => (
                                <li key={o.id} className="text-sm leading-relaxed">
                                  <span>{o.text}</span>
                                  {o.certainty === "inferred" && (
                                    <span className="block text-xs text-muted mt-1 pl-3
                                                     border-l-2 border-accent/40">
                                      KRYteria read this between the lines rather than
                                      being told it
                                      {o.hedge ? <> — “{o.hedge}”</> : "."}
                                    </span>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        );
                      })}

                      {detail && detail.evidence_links?.length > 0 && (
                        <div>
                          <Eyebrow>What this bears on</Eyebrow>
                          <p className="text-xs text-faint mt-1">
                            Which of your criteria this entry speaks to, and how. Nothing
                            here changes an assessment — that stays yours to set.
                          </p>
                          <ul className="mt-3 space-y-2.5">
                            {detail.evidence_links.map((m) => (
                              <li key={m.id} className="text-sm">
                                <span className="flex items-baseline gap-2 flex-wrap">
                                  <RelationPill relation={m.relation} />
                                  <span>{m.criterion_value}</span>
                                </span>
                                {m.rationale && (
                                  <span className="block text-xs text-muted mt-1">
                                    {m.rationale}
                                  </span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {detail && detail.questions?.length > 0 && (
                        <div>
                          <Eyebrow>What it asked you</Eyebrow>
                          <p className="text-xs text-faint mt-1">
                            Questions about the claim, never about you. Answering is
                            optional and declining costs nothing.
                          </p>
                          <ul className="mt-3 space-y-4">
                            {detail.questions.map((q) => (
                              <li key={q.id} className="text-sm">
                                <span className="block text-muted text-xs">
                                  on “{q.claim}”
                                </span>
                                <span className="block mt-1 leading-relaxed">
                                  {q.question}
                                </span>
                                {q.answer && (
                                  <span className="block text-xs text-muted mt-1">
                                    You said: {q.answer}
                                  </span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}
