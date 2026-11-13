/**
 * The only place the browser talks to the backend.
 *
 * Note what is absent: no account id is ever sent. The session cookie carries it, which
 * is what makes it impossible for this client to ask for somebody else's data even by
 * mistake. `credentials: "same-origin"` is the whole auth story.
 */

export type Tier = "mandatory" | "preferred" | "aspirational";
export type Status = "pass" | "unknown" | "fail" | "not_applicable";
export type Relation = "supporting" | "contradicting" | "complicating" | "unrelated";
export type Retention = "discard" | "analysis_only" | "keep_all";
export type Choice =
  | "talk" | "boundary" | "more_time" | "gather_info"
  | "reconsider" | "revise_criterion" | "undecided";

export interface Account {
  id: number;
  handle: string;
  tone_mode: string;
  theme: "dark" | "warm";
  resource_offering: "proactive" | "on_request" | "suppressed";
  retention: Retention;
  /** ISO 3166-1 alpha-2, or null for "not said". Set by her, never inferred. */
  region: string | null;
  is_demo: number;
}

export interface Criterion {
  id: number;
  value: string;
  desired_behavior: string;
  why_it_matters: string | null;
  version: number;
  lineage_id: string;
  status: string;
  examples: string[];
  revision_note?: string | null;
  created_at: string;
}

export interface ProfileCriterion extends Criterion {
  criterion_id: number;
  tier: Tier;
  relevance: "relevant" | "not_applicable";
  assessment?: Status;
}

export interface Profile {
  id: number;
  name: string;
  objective: string | null;
  context_label: string | null;
  criteria_count?: number;
  archived_at: string | null;
}

export interface Person { id: number; alias: string; role_label: string | null }

export interface Entry {
  id: number;
  occurred_on: string;
  entry_mode: string;
  body: string | null;
  what_happened: string | null;
  original_erased_at: string | null;
  retention: Retention;
  people?: string[];
}

export interface Observation {
  id: number;
  kind: "reported_event" | "interpretation" | "emotional_reaction"
      | "missing_information" | "uncertainty";
  text: string;
  certainty: "stated" | "inferred";
  hedge: string | null;
}

export interface Pattern {
  id: number;
  kind: string;
  statement: string;
  support_count: number;
  contra_count: number;
  evidence_strength: "insufficient" | "limited" | "moderate" | "strong";
  gap_note: string | null;
  uncertainties: string[];
  alternatives: string[];
  status: string;
  evidence: { entry_id: number; occurred_on: string; excerpt: string }[];
  counter_evidence: { entry_id: number; occurred_on: string; excerpt: string }[];
}

export interface Analysis {
  run_id: number;
  status: string;
  halted: boolean;
  model_calls: number;
  errors: string[];
  safety?: {
    concern_detected: boolean;
    category: string | null;
    concern_level: string;
    acknowledgement: string | null;
    safety_check: string | null;
    rationale: string | null;
  };
  resources?: Resource[];
  emergency_note?: string;
  halt_reason?: string;
  observations?: Observation[];
  missing_information?: string[];
  uncertainties?: string[];
  mappings?: { criterion_id: number; observation_index: number; relation: Relation; rationale: string | null }[];
  insufficient?: { criterion_id: number; why: string }[];
  unmapped?: number[];
  questions?: { claim: string; question: string; gap_kind: string; materiality: string }[];
  cross_criterion?: { explanation: string; competing: boolean; competing_question: string | null }[];
  patterns?: unknown[];
  reflection?: Reflection;
}

export interface Reflection {
  context: string | null;
  question: string;
  alternatives: string[];
  options: Choice[];
  is_postponement_probe: boolean;
  reconciliation: { current_feeling: string; broader_evidence: string; tension: string | null } | null;
  cooldown_suggested: boolean;
  cooldown_summary_known: string | null;
  cooldown_summary_unknown: string | null;
  cooldown_would_help: string | null;
}

export interface Resource {
  id: number; name: string; kind: string; phone: string | null;
  text_line: string | null; url: string | null; hours: string | null; note: string | null;
  /** When KRYteria last checked this against the organisation's own page. Shown to the
   *  user: a dated number can be judged, a bare one asks to be trusted. */
  verified_at: string;
  region: string;
}

/** What ticking means, and the four states are not a 0–3 scale. */
export type Relevance = "relevant" | "not_applicable";

export type ChecklistState =
  | "observed" | "not_observed" | "contradicted" | "no_opportunity";

export interface ChecklistItem {
  id: number;
  text: string;
  polarity: "demonstrates" | "contradicts";
  source_level: string;
  research_ref: string | null;
  /** Present only when a person was supplied — counts of what has been recorded. */
  times_observed?: number;
  times_contradicted?: number;
  no_opportunity?: number;
}

export interface Progress {
  active_criteria: number;
  entries: number;
  recent_entries: Entry[];
  open_patterns: Pattern[];
  themes: {
    theme_id: string; label: string; entries: number;
    first_seen: string | null; last_seen: string | null; sensitive: boolean;
  }[];
  insufficient_evidence: Pattern[];
  repeatedly_postponed: { criterion_id: number; value: string; count: number }[];
  changed_priorities: { criterion_id: number; value: string; versions: Criterion[] }[];
  decisions_by_choice: Record<string, number>;
  recent_decisions: { id: number; choice: Choice; action_text: string | null; created_at: string }[];
  unanswered_questions: { id: number; claim: string; question: string }[];
  pending_proposals: unknown[];
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
          // Pydantic's own message, which is about a field and not about the user.
          ? body.detail.map((d: { msg: string }) => d.msg).join("; ")
          : detail;
    } catch { /* a non-JSON error body is not worth a second failure */ }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const get = <T,>(p: string) => call<T>(p);
const post = <T,>(p: string, body?: unknown) =>
  call<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T,>(p: string, body: unknown) =>
  call<T>(p, { method: "PATCH", body: JSON.stringify(body) });
const put = <T,>(p: string, body: unknown) =>
  call<T>(p, { method: "PUT", body: JSON.stringify(body) });
const del = <T,>(p: string) => call<T>(p, { method: "DELETE" });

export const api = {
  health: () => get<Record<string, unknown>>("/api/health"),

  me: () => get<Account>("/api/auth/me"),
  signUp: (handle: string, passphrase: string) =>
    post<Account>("/api/auth/signup", { handle, passphrase }),
  signIn: (handle: string, passphrase: string) =>
    post<Account>("/api/auth/signin", { handle, passphrase }),
  signOut: () => post<{ signed_out: boolean }>("/api/auth/signout"),

  // The demo front door. No passphrase crosses the wire: the backend refuses any handle
  // that is not a demo account, so this cannot open a real person's journal.
  demoCharacters: () => get<Array<{
    handle: string; name: string; age?: number;
    occupation?: string; location?: string; demonstrates?: string[];
  }>>("/api/demo/characters"),
  demoSignIn: (handle: string) => post<Account>("/api/demo/signin", { handle }),

  setPreferences: (
    p: Partial<Pick<Account, "theme" | "tone_mode" | "resource_offering" | "retention">>
      & { region?: string },
  ) => patch<Account>("/api/auth/preferences", p),

  criteria: () => get<Criterion[]>("/api/criteria"),
  createCriterion: (b: { value: string; desired_behavior: string; why_it_matters?: string | null }) =>
    post<Criterion>("/api/criteria", b),
  reviseCriterion: (id: number, b: Record<string, unknown>) =>
    post<Criterion>(`/api/criteria/${id}/revise`, b),
  criterionHistory: (id: number) => get<Criterion[]>(`/api/criteria/${id}/history`),
  retireCriterion: (id: number) => del<unknown>(`/api/criteria/${id}`),

  profiles: () => get<Profile[]>("/api/profiles"),
  createProfile: (b: { name: string; objective?: string | null; context_label?: string | null }) =>
    post<Profile>("/api/profiles", b),
  /** Rename, or change what it's for. Nothing configured under it is touched. */
  updateProfile: (id: number, b: {
    name?: string; objective?: string | null; context_label?: string | null;
  }) => patch<Profile>(`/api/profiles/${id}`, b),
  /** Put away or bring back. There is deliberately no per-profile delete. */
  archiveProfile: (id: number, archived: boolean) =>
    post<{ profile_id: number; archived: boolean; note: string }>(
      `/api/profiles/${id}/archive?archived=${archived}`, {}),
  profilesIncludingArchived: () =>
    get<Profile[]>("/api/profiles?include_archived=true"),

  profileCriteria: (id: number) => get<ProfileCriterion[]>(`/api/profiles/${id}/criteria`),

  // ---------------------------------------------------------------- checklist mode
  checklist: (criterionId: number, q: { profile_id?: number; person_id?: number } = {}) => {
    const p = new URLSearchParams();
    if (q.profile_id != null) p.set("profile_id", String(q.profile_id));
    if (q.person_id != null) p.set("person_id", String(q.person_id));
    const qs = p.toString();
    return get<ChecklistItem[]>(
      `/api/criteria/${criterionId}/checklist${qs ? `?${qs}` : ""}`);
  },
  generateChecklist: (criterionId: number, profile_id?: number) =>
    post<{
      clarification: string | null; ambiguities: string[];
      indicators: ChecklistItem[]; saved: number;
    }>(`/api/criteria/${criterionId}/checklist/generate`,
      { criterion_id: criterionId, profile_id: profile_id ?? null }),
  observeIndicator: (itemId: number, b: {
    person_id?: number | null; state: ChecklistState; note?: string | null;
  }) => post<{ id: number }>(`/api/checklist/${itemId}/observe`, b),
  addToProfile: (id: number, b: { criterion_id: number; tier?: Tier; relevance?: string }) =>
    post<ProfileCriterion[]>(`/api/profiles/${id}/criteria`, b),
  setTier: (profileId: number, criterionId: number, tier: Tier) =>
    patch<ProfileCriterion[]>(`/api/profiles/${profileId}/criteria/${criterionId}`, { tier }),
  /** Relevance is per profile, like the tier. Changing it never touches another. */
  setRelevance: (profileId: number, criterionId: number, relevance: Relevance) =>
    patch<ProfileCriterion[]>(
      `/api/profiles/${profileId}/criteria/${criterionId}`, { relevance }),
  copyCriteria: (targetId: number, sourceId: number) =>
    post<{ copied: number }>(`/api/profiles/${targetId}/copy-criteria`, { source_profile_id: sourceId }),

  people: () => get<Person[]>("/api/people"),
  createPerson: (alias: string, role_label?: string) =>
    post<Person>("/api/people", { alias, role_label }),
  personFootprint: (id: number) =>
    get<{ entries: number; assessments: number; evidence_links: number }>(
      `/api/people/${id}/footprint`),
  deletePerson: (id: number, deleteEntries = false) =>
    del<{ assessments_removed: number; entries_removed: number; note: string }>(
      `/api/people/${id}?delete_entries=${deleteEntries}`),

  entries: (params?: { search?: string; limit?: number }) =>
    get<Entry[]>("/api/entries" + (params?.search ? `?search=${encodeURIComponent(params.search)}` : "")),
  entry: (id: number) => get<Entry & { observations: Observation[] }>(`/api/entries/${id}`),
  brainDump: (b: {
    text: string; profile_id?: number | null; person_id?: number | null;
    want_reflection?: boolean; retention?: Retention | null; analyze?: boolean;
  }) => post<{ entry: Entry; analysis: Analysis | null; retention: { retention: Retention; original_erased: boolean }; note?: string }>("/api/brain-dump", b),
  setEntryRetention: (id: number, retention: Retention, apply_to_past = false) =>
    post<{ original_erased: boolean; note: string }>(`/api/entries/${id}/retention`, { retention, apply_to_past }),
  retentionReport: () => get<Record<string, unknown>>("/api/retention"),

  assessments: (profileId: number, personId: number) =>
    get<ProfileCriterion[]>(`/api/assessments?profile_id=${profileId}&person_id=${personId}`),
  setAssessment: (b: { profile_id: number; criterion_id: number; person_id: number; status: Status; note?: string }) =>
    put<{ assessment_id: number; status: Status }>("/api/assessments", b),

  patterns: (profileId?: number) =>
    get<Pattern[]>("/api/patterns" + (profileId ? `?profile_id=${profileId}` : "")),
  proposals: () => get<{ id: number; criterion_value: string; person_alias: string; current_status: string; proposed_status: string; rationale: string }[]>("/api/proposals"),
  decideProposal: (id: number, resolution: string, final_status?: Status) =>
    post<unknown>(`/api/proposals/${id}/decide`, { resolution, final_status }),

  decisions: () => get<Progress["recent_decisions"]>("/api/decisions"),
  recordDecision: (b: { choice: Choice; action_text?: string | null; criterion_id?: number | null }) =>
    post<{ postponements_on_this_concern: number; probe_available: boolean }>("/api/decisions", b),

  /** "I logged it quickly — now actually read it." Never automatic. */
  analyseEntry: (entryId: number, b: {
    profile_id?: number | null; person_id?: number | null; want_reflection?: boolean;
  }) => post<{ entry: Entry; analysis: Analysis | null }>(
    `/api/entries/${entryId}/analyse`, b),

  progress: () => get<Progress>("/api/progress"),
  themesFor: (personId?: number | null) =>
    get<{
      person_id: number | null;
      themes: { theme_id: string; label: string; about: string; sensitive: boolean;
                entries: number; first_seen: string | null; last_seen: string | null }[];
    }>(`/api/themes${personId ? `?person_id=${personId}` : ""}`),
  usage: () => get<Record<string, unknown>>("/api/usage"),
  resources: () =>
    get<{
      region: string | null;
      region_source: "query" | "account" | "unset";
      resources: Resource[];
      note: string | null;
      emergency_note: string;
      staleness_note: string | null;
    }>("/api/resources"),
  export: () => get<unknown>("/api/export"),
  deleteAccount: (passphrase: string) =>
    post<{ deleted: boolean }>("/api/account/delete", { passphrase, confirm: "DELETE EVERYTHING" }),
};
