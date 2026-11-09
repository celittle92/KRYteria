import { useEffect, useState } from "react";
import { api, type Choice } from "../api";
import { Card, DECISION_COPY, Empty, ErrorNote, Eyebrow, Section, Spinner } from "../components/ui";

/**
 * Where open questions wait, and where a decision gets recorded.
 *
 * The signature question lives here. When it appears it is asked plainly, once, with no
 * countdown and no recommendation after it — and choosing to wait again is recorded
 * exactly like any other decision.
 */
export default function Reflection() {
  const [questions, setQuestions] = useState<{ id: number; claim: string; question: string }[]>([]);
  const [proposals, setProposals] = useState<Awaited<ReturnType<typeof api.proposals>>>([]);
  const [postponed, setPostponed] = useState<{ criterion_id: number; value: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [p, pr] = await Promise.all([api.progress(), api.proposals()]);
    setQuestions(p.unanswered_questions);
    setPostponed(p.repeatedly_postponed.filter((r) => r.count >= 3));
    setProposals(pr);
  }

  useEffect(() => { refresh().catch((e) => setError(String(e))).finally(() => setLoading(false)); }, []);

  if (loading) return <Spinner label="Gathering what's open" />;

  const nothing = questions.length === 0 && proposals.length === 0 && postponed.length === 0;

  return (
    <div>
      {error && <div className="mb-6"><ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote></div>}

      {nothing && (
        <Section title="Reflection" subtitle="Questions, suggestions, and decisions waiting on you.">
          <Empty>
            Nothing is waiting. There's no backlog here and nothing is overdue — this page
            fills up only when KRYteria has something real to ask.
          </Empty>
        </Section>
      )}

      {postponed.length > 0 && (
        <Section title="You've come back to this" subtitle="Noted, not judged. Waiting is a decision like any other.">
          <div className="space-y-4">
            {postponed.map((p) => (
              <Probe key={p.criterion_id} concern={p} onRecorded={refresh} />
            ))}
          </div>
        </Section>
      )}

      {questions.length > 0 && (
        <Section
          title="Worth pinning down"
          subtitle="Things KRYteria couldn't settle from what you wrote. Answer if it helps; skip if it doesn't."
        >
          <div className="space-y-4">
            {questions.map((q) => (
              <Question key={q.id} question={q} onDone={refresh} />
            ))}
          </div>
        </Section>
      )}

      {proposals.length > 0 && (
        <Section
          title="Suggested changes"
          subtitle="KRYteria thinks these statuses might have moved. Nothing changes until you say so."
        >
          <div className="space-y-4">
            {proposals.map((p) => (
              <Proposal key={p.id} proposal={p} onDone={refresh} />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Probe({ concern, onRecorded }: {
  concern: { criterion_id: number; value: string; count: number };
  onRecorded: () => void;
}) {
  const [done, setDone] = useState<string | null>(null);

  async function record(choice: Choice) {
    await api.recordDecision({ choice, criterion_id: concern.criterion_id });
    setDone(choice);
    onRecorded();
  }

  return (
    <Card className="p-6 sm:p-7">
      <Eyebrow>What you've recorded</Eyebrow>
      <p className="text-muted text-sm">
        You've chosen to give <span className="text-ink">{concern.value.toLowerCase()}</span>{" "}
        more time {concern.count} times.
      </p>

      <p className="voice text-xl sm:text-2xl mt-6 leading-snug">
        What new information are you waiting for that you don't already have?
      </p>

      {done ? (
        <p className="text-sm text-muted mt-6">
          Recorded. {done === "more_time"
            ? "That's a legitimate answer, and it's yours to make."
            : "Noted."}
        </p>
      ) : (
        <div className="mt-6 space-y-2">
          {(["talk", "boundary", "gather_info", "more_time", "undecided"] as Choice[]).map((c) => (
            <button key={c} className="choice" onClick={() => record(c)}>
              {DECISION_COPY[c]}
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

function Question({ question, onDone }: {
  question: { id: number; claim: string; question: string };
  onDone: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(text: string | null) {
    setBusy(true);
    try {
      await fetch(`/api/questions/${question.id}/answer`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: text }),
      });
      onDone();
    } finally { setBusy(false); }
  }

  return (
    <Card className="p-6">
      <p className="text-sm text-faint italic">"{question.claim}"</p>
      <p className="voice text-lg mt-2">{question.question}</p>
      <textarea
        className="field mt-4 min-h-[80px]"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder="However much or little you want to say"
      />
      <div className="flex gap-3 mt-4">
        <button className="btn-accent" disabled={busy || !answer.trim()}
                onClick={() => send(answer)}>
          Answer
        </button>
        <button className="btn-quiet" disabled={busy} onClick={() => send(null)}>
          Skip this
        </button>
      </div>
    </Card>
  );
}

function Proposal({ proposal, onDone }: {
  proposal: { id: number; criterion_value: string; person_alias: string; current_status: string; proposed_status: string; rationale: string };
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function decide(resolution: string, final?: string) {
    setBusy(true);
    try {
      await api.decideProposal(proposal.id, resolution, final as never);
      onDone();
    } finally { setBusy(false); }
  }

  return (
    <Card className="p-6">
      <p className="text-ink">
        {proposal.criterion_value} — {proposal.person_alias}
      </p>
      <p className="text-sm text-muted mt-1">
        {proposal.current_status} → {proposal.proposed_status}
      </p>
      <p className="text-sm text-muted mt-3 leading-relaxed">{proposal.rationale}</p>
      <div className="flex flex-wrap gap-3 mt-5">
        <button className="btn-accent" disabled={busy} onClick={() => decide("accepted")}>
          Accept
        </button>
        <button className="btn-quiet" disabled={busy} onClick={() => decide("rejected")}>
          No, leave it
        </button>
        <button className="btn-quiet" disabled={busy}
                onClick={() => decide("edited", "unknown")}>
          Set it to Unknown instead
        </button>
      </div>
    </Card>
  );
}
