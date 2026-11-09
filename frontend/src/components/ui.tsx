/**
 * The vocabulary the mockups establish, in one place.
 *
 * Two rules govern everything here:
 *
 *   No scores. There is no component that renders a percentage, a rating, or a progress
 *   bar over a person. Counts are shown as counts, in words.
 *
 *   No alarm. "Contradicting" is clay, not red. Nothing pulses or flashes. Somebody
 *   reading that evidence cuts against what they hoped should not also be looking at a
 *   warning triangle.
 */

import type { ReactNode } from "react";
import type { Relation, Retention, Status, Tier } from "../api";

export function Pill({ tone = "neutral", children }: {
  tone?: "neutral" | "accent" | "support" | "contradict" | "complicate" | "strong";
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    neutral: "bg-line/50 text-muted",
    accent: "bg-accent/15 text-accent",
    support: "bg-support/15 text-support",
    contradict: "bg-contradict/15 text-contradict",
    complicate: "bg-complicate/15 text-complicate",
    strong: "bg-ink text-ground",
  };
  return <span className={`pill ${tones[tone]}`}>{children}</span>;
}

/** Mandatory reads strongest, aspirational quietest — the mockups' own hierarchy. */
export function TierPill({ tier }: { tier: Tier }) {
  const map: Record<Tier, { tone: "accent" | "neutral"; label: string }> = {
    mandatory: { tone: "accent", label: "Mandatory" },
    preferred: { tone: "neutral", label: "Preferred" },
    aspirational: { tone: "neutral", label: "Aspirational" },
  };
  const { tone, label } = map[tier];
  return <Pill tone={tone}>{label}</Pill>;
}

/** Four statuses, and Unknown is never styled as an absence. */
export function StatusPill({ status }: { status: Status }) {
  const map: Record<Status, { tone: "support" | "neutral" | "contradict"; label: string }> = {
    pass: { tone: "support", label: "Pass" },
    unknown: { tone: "neutral", label: "Unknown" },
    fail: { tone: "contradict", label: "Fail" },
    not_applicable: { tone: "neutral", label: "Not applicable" },
  };
  const { tone, label } = map[status];
  return <Pill tone={tone}>{label}</Pill>;
}

export function RelationPill({ relation }: { relation: Relation }) {
  const map: Record<Relation, { tone: "support" | "contradict" | "complicate" | "neutral"; label: string }> = {
    supporting: { tone: "support", label: "Supporting evidence" },
    contradicting: { tone: "contradict", label: "Contradicting evidence" },
    complicating: { tone: "complicate", label: "Complicating — needs context" },
    unrelated: { tone: "neutral", label: "Unrelated" },
  };
  const { tone, label } = map[relation];
  return <Pill tone={tone}>{label}</Pill>;
}

/** Qualitative, never numeric. "Insufficient" is a result, so it is shown as one. */
export function StrengthPill({ strength }: { strength: string }) {
  const map: Record<string, { tone: "neutral" | "complicate" | "support"; label: string }> = {
    insufficient: { tone: "neutral", label: "Insufficient evidence" },
    limited: { tone: "neutral", label: "Limited evidence" },
    moderate: { tone: "complicate", label: "Moderate evidence" },
    strong: { tone: "support", label: "Strong evidence" },
  };
  const { tone, label } = map[strength] ?? map.limited;
  return <Pill tone={tone}>{label}</Pill>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="eyebrow mb-2">{children}</div>;
}

/** The quoted block from the mockups — "YOUR STATED CRITERIA" and its quotation. */
export function Quoted({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Eyebrow>{label}</Eyebrow>
      <blockquote className="voice text-lg sm:text-xl leading-relaxed text-ink">
        {children}
      </blockquote>
    </div>
  );
}

export function Section({ title, subtitle, action, children }: {
  title: string; subtitle?: string; action?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="mb-12">
      <div className="flex items-end justify-between gap-4 mb-5">
        <div>
          <h2 className="font-serif text-2xl">{title}</h2>
          {subtitle && <p className="text-sm text-muted mt-1 max-w-reading">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/**
 * An empty state that says what *would* fill it.
 *
 * Deliberately never scolds and never nudges: a person who writes nothing this week has
 * not failed at anything, and this product does not optimise for engagement.
 */
export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="border border-dashed border-line rounded-card px-6 py-10 text-center">
      <p className="text-muted text-sm max-w-reading mx-auto">{children}</p>
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-muted text-sm" role="status" aria-live="polite">
      <span className="inline-block w-3 h-3 rounded-full border-2 border-line border-t-accent animate-spin" />
      {label}
    </div>
  );
}

export function ErrorNote({ children, onDismiss }: { children: ReactNode; onDismiss?: () => void }) {
  return (
    <div className="border border-contradict/40 bg-contradict/10 rounded-xl px-4 py-3 text-sm flex gap-3"
         role="alert">
      <span className="flex-1 text-ink">{children}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="text-muted hover:text-ink" aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  );
}

export const RETENTION_COPY: Record<Retention, { title: string; detail: string }> = {
  discard: {
    title: "Don't retain this Brain Dump",
    detail:
      "The original text is discarded after processing, along with what was drawn from " +
      "it. You can read the results now, but neither will be available later.",
  },
  analysis_only: {
    title: "Save the analysis, erase the original",
    detail:
      "Keep the observations, evidence mappings, and confirmed assessment changes, but " +
      "discard the original narrative.",
  },
  keep_all: {
    title: "Save to my private history",
    detail:
      "Keep the original Brain Dump and its associated analysis in your private " +
      "account, until you delete them.",
  },
};

export const DECISION_COPY: Record<string, string> = {
  talk: "Talk about it",
  boundary: "Set a boundary",
  more_time: "Give it more time",
  gather_info: "Gather more information",
  reconsider: "Reconsider the relationship",
  revise_criterion: "Revise a criterion",
  undecided: "I don't know yet",
};

export const OBSERVATION_COPY: Record<string, string> = {
  reported_event: "What happened",
  interpretation: "What you made of it",
  emotional_reaction: "How it landed",
  missing_information: "Not yet known",
  uncertainty: "Still uncertain",
};
