-- KRYteria schema.
--
-- Design notes that are load-bearing, not commentary:
--
--  * Criteria are VERSIONED, never updated in place. A revision inserts a new row sharing
--    the old row's lineage_id and sets the old row's superseded_at. "How my standards
--    changed over time" is the whole point of the My Progress screen, and an UPDATE
--    destroys it.
--  * Observations carry a `kind` that separates what the user reported from what anyone
--    interpreted. Nothing in this schema lets an interpretation become a reported_event.
--  * People exist only as user-chosen aliases. There is no column for a real name.
--  * Domains are rows, not an enum, so a new area of life needs no migration.
--  * No table stores a score, rating, or percentage for a person or a relationship.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- accounts

CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY,
    handle          TEXT    NOT NULL UNIQUE,     -- user-chosen, anonymous. No email, no name.
    passphrase_hash TEXT    NOT NULL,            -- Argon2id, via pwdlib. Never returned.
    -- V1 ships Clarity Mode only. Tough Love is V2 and explicitly not an MVP priority;
    -- the value is allowed here so the column need not migrate, but nothing selects it yet.
    -- Tone changes presentation, never reasoning, evidence, or an assessment outcome.
    tone_mode       TEXT    NOT NULL DEFAULT 'clarity'
                            CHECK (tone_mode IN ('clarity', 'tough_love')),
    theme           TEXT    NOT NULL DEFAULT 'dark'
                            CHECK (theme IN ('dark', 'warm')),
    is_demo         INTEGER NOT NULL DEFAULT 0,  -- synthetic. Never mixed with real records.
    timezone        TEXT    NOT NULL DEFAULT 'UTC',
    -- How the user wants support resources handled. Theirs to set, and it is honoured.
    -- `on_request` and `suppressed` still leave the safety layer fully active; they
    -- govern unsolicited offering, nothing else.
    resource_offering TEXT  NOT NULL DEFAULT 'proactive'
                            CHECK (resource_offering IN ('proactive', 'on_request',
                                                         'suppressed')),
    -- What KRYteria keeps after a brain dump has been processed. The user's default,
    -- settable once in settings rather than answered every time; each dump may override
    -- it. `analysis_only` is the interesting one: somebody may want to keep the fact
    -- that they noticed a pattern without keeping the intimate 2,000-word account they
    -- wrote at 1 a.m.
    retention       TEXT    NOT NULL DEFAULT 'analysis_only'
                            CHECK (retention IN ('discard', 'analysis_only', 'keep_all')),
    created_at      TEXT    NOT NULL,
    updated_at      TEXT,
    last_seen_at    TEXT
);

-- ---------------------------------------------------------------- domains

CREATE TABLE IF NOT EXISTS domains (
    id         INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,                 -- user-facing, e.g. "Dating", "My sister"
    kind       TEXT    NOT NULL                  -- romantic first, but never the only one
                       CHECK (kind IN ('romantic', 'friendship', 'family',
                                       'work', 'personal', 'other')),
    created_at TEXT    NOT NULL,
    archived_at TEXT,
    UNIQUE (account_id, name)
);

-- ---------------------------------------------------------------- people (aliases only)

CREATE TABLE IF NOT EXISTS people (
    id         INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    domain_id  INTEGER REFERENCES domains(id) ON DELETE SET NULL,
    alias      TEXT    NOT NULL,                 -- the ONLY identifier. Never a real name.
    role_label TEXT,                             -- "the person I'm seeing", "my manager"
    created_at TEXT    NOT NULL,
    UNIQUE (account_id, alias)
);

-- ---------------------------------------------------------------- criteria (versioned)

-- LEVEL 1 OF THREE: the Master Criteria Library.
--
-- A criterion here is a reusable personal standard and NOTHING ELSE. It carries no tier
-- and belongs to no profile, because the same standard matters differently depending on
-- what the user is looking for — physical attraction can be Preferred for a husband and
-- Mandatory for a boyfriend, and both are legitimate. The tier lives on profile_criteria.
CREATE TABLE IF NOT EXISTS criteria (
    id                INTEGER PRIMARY KEY,
    account_id        INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    lineage_id        TEXT    NOT NULL,          -- stable across every version of one criterion
    version           INTEGER NOT NULL DEFAULT 1,
    value             TEXT    NOT NULL,          -- the personal value, e.g. "Follow-through"
    desired_behavior  TEXT    NOT NULL,          -- what meeting it looks like in practice
    why_it_matters    TEXT,
    examples_json     TEXT    NOT NULL DEFAULT '[]',
    status            TEXT    NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active', 'superseded', 'retired')),
    revision_note     TEXT,                      -- why the user changed it, in their words
    created_at        TEXT    NOT NULL,
    superseded_at     TEXT,
    UNIQUE (lineage_id, version)
);

CREATE INDEX IF NOT EXISTS idx_criteria_active
    ON criteria (account_id, status);
CREATE INDEX IF NOT EXISTS idx_criteria_lineage
    ON criteria (lineage_id, version);

-- ---------------------------------------------------------------- KRYteria profiles

-- LEVEL 2 OF THREE: a saved configuration for one relationship objective.
--
-- "Husband KRYteria", "Boyfriend KRYteria", "Fuck Buddy KRYteria", "One Night Stand
-- KRYteria" — and equally "Manager KRYteria" or "Close Friend KRYteria". Each is
-- independent.
--
-- NO PROFILE RANKS ABOVE ANOTHER. Nothing in this schema or anywhere above it may treat
-- a long-term profile as the "real" one, treat failing it as a defect, or carry a
-- standard from one profile into another. A person can be a wonderful casual partner
-- without being someone the user wants to marry; that is not a contradiction and the app
-- never presents it as one.
CREATE TABLE IF NOT EXISTS profiles (
    id            INTEGER PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    domain_id     INTEGER REFERENCES domains(id) ON DELETE SET NULL,
    name          TEXT    NOT NULL,              -- the user's own label
    objective     TEXT,                          -- what they want from this kind of connection
    context_label TEXT,                          -- "Long-term", "Dating", "One-time", …
    sort_order    INTEGER NOT NULL DEFAULT 0,
    archived_at   TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT,
    UNIQUE (account_id, name)
);

-- The join that makes a profile a configuration rather than a copy: it SELECTS criteria
-- from the master library and assigns this profile's own tier and relevance.
--
-- `copied_from_profile_id` records provenance when the user duplicates a criterion's
-- settings from another profile. It is a record of where the settings came from, never a
-- live link — changing one profile must never silently change another.
CREATE TABLE IF NOT EXISTS profile_criteria (
    id                     INTEGER PRIMARY KEY,
    profile_id             INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    criterion_id           INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    -- Dimension 1, and it is per profile. The user sets it; nothing questions it.
    tier                   TEXT    NOT NULL DEFAULT 'preferred'
                                   CHECK (tier IN ('mandatory', 'preferred', 'aspirational')),
    relevance              TEXT    NOT NULL DEFAULT 'relevant'
                                   CHECK (relevance IN ('relevant', 'not_applicable')),
    sort_order             INTEGER NOT NULL DEFAULT 0,
    copied_from_profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
    created_at             TEXT    NOT NULL,
    UNIQUE (profile_id, criterion_id)
);

CREATE INDEX IF NOT EXISTS idx_profile_criteria
    ON profile_criteria (profile_id, tier);

-- ---------------------------------------------------------------- assessments

-- LEVEL 3 OF THREE: evidence about one person, judged against ONE SELECTED PROFILE.
--
-- Dimension 2 of the KRYteria system. The status belongs to the
-- (profile, criterion, person) triple, not to the criterion. The same person assessed
-- under Husband KRYteria and under Fuck Buddy KRYteria has two independent answers, and
-- neither contradicts the other. This is also what makes "am I making exceptions for
-- someone I wouldn't make for anyone else?" answerable.
--
-- `unknown` is the default and the honest starting state. `not_applicable` means the
-- criterion is not relevant to this profile — a real answer, not a dodge.
--
-- THE AGENT NEVER WRITES THIS TABLE. A proposed change goes to assessment_proposals and
-- waits for the user. That is why these are two tables rather than one with a flag: the
-- rule "the agent shouldn't silently change a criterion's status" is then structural.
CREATE TABLE IF NOT EXISTS assessments (
    id           INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    profile_id   INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    person_id    INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    status       TEXT    NOT NULL DEFAULT 'unknown'
                         CHECK (status IN ('pass', 'unknown', 'fail', 'not_applicable')),
    note         TEXT,                           -- the user's own words, if they added any
    updated_at   TEXT    NOT NULL,
    UNIQUE (profile_id, criterion_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_assessments_person
    ON assessments (account_id, person_id, profile_id);

-- Every status change, kept. Required by the spec: previous status, new status,
-- timestamp, origin, explanation. This is also the My Progress screen's raw material —
-- "how my reading of this person changed as evidence arrived" is only answerable if the
-- transitions survive.
CREATE TABLE IF NOT EXISTS assessment_history (
    id              INTEGER PRIMARY KEY,
    assessment_id   INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    previous_status TEXT,
    new_status      TEXT    NOT NULL,
    origin          TEXT    NOT NULL
                            CHECK (origin IN ('user', 'user_accepted_proposal',
                                              'user_edited_proposal', 'system_initial')),
    explanation     TEXT,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assessment_history
    ON assessment_history (assessment_id, created_at);

-- What the agent suggested, and what the user did about it. An un-actioned row is a
-- pending proposal the UI shows for accept / reject / edit.
CREATE TABLE IF NOT EXISTS assessment_proposals (
    id             INTEGER PRIMARY KEY,
    account_id     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    profile_id     INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    criterion_id   INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    person_id      INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    current_status TEXT    NOT NULL,
    proposed_status TEXT   NOT NULL
                           CHECK (proposed_status IN ('pass', 'unknown', 'fail',
                                                      'not_applicable')),
    rationale      TEXT    NOT NULL,             -- why, in evidence terms
    run_id         INTEGER,
    resolution     TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (resolution IN ('pending', 'accepted', 'rejected', 'edited')),
    resolved_at    TEXT,
    created_at     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_proposals_pending
    ON assessment_proposals (account_id, resolution);

-- ---------------------------------------------------------------- journal entries

CREATE TABLE IF NOT EXISTS entries (
    id               INTEGER PRIMARY KEY,
    account_id       INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    domain_id        INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    occurred_on      TEXT    NOT NULL,           -- the day it happened, not the day it was typed
    entry_mode       TEXT    NOT NULL            -- both are first-class; neither is a fallback
                             CHECK (entry_mode IN ('free', 'structured')),
    body             TEXT,                       -- free-text dump / post-date debrief
    what_happened    TEXT,                       -- structured fields, all optional
    what_expected    TEXT,
    how_it_affected  TEXT,
    witness          TEXT    NOT NULL DEFAULT 'firsthand'
                             CHECK (witness IN ('firsthand', 'inferred', 'secondhand')),
    -- What was decided for THIS entry, which may differ from the account default.
    retention        TEXT    NOT NULL DEFAULT 'analysis_only'
                             CHECK (retention IN ('discard', 'analysis_only', 'keep_all')),
    -- When the original narrative was actually erased. The row survives so its
    -- observations, mappings and assessments keep something to point at — the entry
    -- becomes a dated placeholder rather than disappearing and orphaning its evidence.
    original_erased_at TEXT,
    created_at       TEXT    NOT NULL,
    deleted_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_entries_account
    ON entries (account_id, domain_id, occurred_on DESC);

CREATE TABLE IF NOT EXISTS entry_people (
    entry_id  INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, person_id)
);

-- The user's own link from an entry to a criterion. Distinct from anything the model infers.
CREATE TABLE IF NOT EXISTS entry_criteria (
    entry_id    INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    linked_by   TEXT    NOT NULL DEFAULT 'user'
                        CHECK (linked_by IN ('user', 'agent')),
    PRIMARY KEY (entry_id, criterion_id)
);

-- ---------------------------------------------------------------- observations

-- The Evidence agent's structured read of an entry. `kind` is the firewall between what
-- happened and what someone made of it. An agent may never write a row that upgrades an
-- interpretation to a reported_event; see backend/store.py.
CREATE TABLE IF NOT EXISTS observations (
    id           INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    entry_id     INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    kind         TEXT    NOT NULL
                         CHECK (kind IN ('reported_event', 'interpretation',
                                         'emotional_reaction', 'missing_information',
                                         'uncertainty')),
    text         TEXT    NOT NULL,
    attributed_to TEXT   NOT NULL DEFAULT 'user'   -- 'user' = they wrote it; 'agent' = extracted
                         CHECK (attributed_to IN ('user', 'agent')),
    -- "Infer, but don't presume." The agent may read between the lines — a user should not
    -- have to name a behaviour correctly before the app can help them look at it — but a
    -- reading is marked as one. `inferred` renders hedged ("it sounds like…", "I may be
    -- reading between the lines"); `stated` is the user's own words and never hedged.
    certainty    TEXT    NOT NULL DEFAULT 'stated'
                         CHECK (certainty IN ('stated', 'inferred')),
    hedge        TEXT,                              -- how to say it, when inferred
    criterion_id INTEGER REFERENCES criteria(id) ON DELETE SET NULL,
    run_id       INTEGER,                          -- which agent run produced it
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_entry
    ON observations (entry_id, kind);

-- ---------------------------------------------------------------- evidence mapping

-- How one observation relates to one criterion for one person. This is the agent's
-- proposed mapping — Direction B, "which of my criteria does this experience inform?"
--
-- `relation` is a DIFFERENT AXIS from observations.kind. The same reported_event can be
-- supporting for one criterion and unrelated to another.
--
-- `complicating` is load-bearing and must never be collapsed into supporting or
-- contradicting: "he got upset, then took time to regulate, then came back and
-- apologised" is relevant and context-dependent, not simply good or bad. An app with only
-- two options forces a verdict the evidence does not support.
-- One observation can legitimately relate to SEVERAL criteria at once, supporting one
-- while complicating another — arriving late for a work reason touches communication,
-- ambition, and respect for time differently. Cross-Criterion Intelligence lives in the
-- fact that these are separate rows with separate relations, never one verdict about a
-- person. Do not collapse them, and do not let one behaviour become evidence about
-- somebody's entire personality.
CREATE TABLE IF NOT EXISTS evidence_links (
    id             INTEGER PRIMARY KEY,
    account_id     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    -- The same evidence reads differently depending on what the user is looking for, so
    -- a link is always interpreted within one profile.
    profile_id     INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
    observation_id INTEGER REFERENCES observations(id) ON DELETE CASCADE,
    entry_id       INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    criterion_id   INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    person_id      INTEGER REFERENCES people(id) ON DELETE SET NULL,
    relation       TEXT    NOT NULL
                           CHECK (relation IN ('supporting', 'contradicting',
                                               'complicating', 'unrelated')),
    rationale      TEXT,                         -- why, in the agent's words
    -- Which of the three epistemic levels this rests on. A contextual hypothesis must
    -- never be shown with the authority of an established research finding.
    source_level   TEXT    NOT NULL DEFAULT 'agent_hypothesis'
                           CHECK (source_level IN ('established_research',
                                                   'research_informed',
                                                   'agent_hypothesis',
                                                   'user_stated')),
    research_ref   TEXT,                         -- citation, when source_level is research
    proposed_by    TEXT    NOT NULL DEFAULT 'agent'
                           CHECK (proposed_by IN ('agent', 'user')),
    -- The user accepts, rejects or edits every agent-proposed mapping.
    resolution     TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (resolution IN ('pending', 'accepted', 'rejected', 'edited')),
    run_id         INTEGER,
    created_at     TEXT    NOT NULL,
    resolved_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_evidence_links_criterion
    ON evidence_links (account_id, criterion_id, relation);
CREATE INDEX IF NOT EXISTS idx_evidence_links_pending
    ON evidence_links (account_id, resolution);

-- ---------------------------------------------------------------- checklist mode

-- Direction A, "criteria → behaviours": the agent turns a criterion into observable
-- behavioural indicators, for users who would rather tick boxes than write paragraphs.
-- Same behavioural intelligence as the brain dump, run the other way round.
CREATE TABLE IF NOT EXISTS checklist_items (
    id           INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    -- Indicators are per profile: what "good communication" looks like for a husband and
    -- for a one-night stand are not the same observable behaviours.
    profile_id   INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
    text         TEXT    NOT NULL,               -- "Can disagree without becoming hostile"
    polarity     TEXT    NOT NULL DEFAULT 'demonstrates'
                         CHECK (polarity IN ('demonstrates', 'contradicts')),
    source_level TEXT    NOT NULL DEFAULT 'research_informed'
                         CHECK (source_level IN ('established_research',
                                                 'research_informed',
                                                 'agent_hypothesis',
                                                 'user_stated')),
    research_ref TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1,     -- the user can remove an indicator
    sort_order   INTEGER NOT NULL DEFAULT 0,
    run_id       INTEGER,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_checklist_criterion
    ON checklist_items (account_id, criterion_id, is_active);

-- TICKING AN ITEM RECORDS AN OBSERVATION. IT DOES NOT ESTABLISH THAT THE CRITERION PASSES.
-- That is why this table exists and why there is no `passes` column on checklist_items:
-- there is no code path from a tick to an assessment status. Only the user sets Pass.
CREATE TABLE IF NOT EXISTS checklist_observations (
    id                INTEGER PRIMARY KEY,
    account_id        INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    checklist_item_id INTEGER NOT NULL REFERENCES checklist_items(id) ON DELETE CASCADE,
    person_id         INTEGER REFERENCES people(id) ON DELETE SET NULL,
    entry_id          INTEGER REFERENCES entries(id) ON DELETE SET NULL,
    -- Four states, not a checkbox. "I never had the chance to see" is different from
    -- "I looked and it wasn't there", and collapsing them manufactures absence of
    -- evidence into evidence of absence.
    state             TEXT    NOT NULL DEFAULT 'observed'
                              CHECK (state IN ('observed', 'not_observed',
                                               'contradicted', 'no_opportunity')),
    note              TEXT,
    occurred_on       TEXT    NOT NULL,
    created_at        TEXT    NOT NULL
);

-- ---------------------------------------------------------------- calendar + timeline

-- THE CALENDAR IS OPTIONAL. Christine's rule: a user must be able to use KRYteria
-- spontaneously without maintaining a dating schedule. Nothing in the app may require an
-- event to exist before an entry, a reflection, or an assessment can be recorded.
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    person_id     INTEGER REFERENCES people(id) ON DELETE SET NULL,
    profile_id    INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
    title         TEXT,
    scheduled_for TEXT    NOT NULL,
    occurred      INTEGER NOT NULL DEFAULT 0,
    note          TEXT,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_account ON events (account_id, scheduled_for);

-- The Date Reflection Timeline: the same experience revisited as the immediate high or
-- low wears off. Three stages, because what stands out two hours afterwards and what
-- stands out a week later are different data, and the difference is itself evidence.
--
-- A stage that is never completed is not a failure; the user owes the app nothing.
CREATE TABLE IF NOT EXISTS reflection_stages (
    id           INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    event_id     INTEGER REFERENCES events(id) ON DELETE CASCADE,
    anchor_entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
    stage        TEXT    NOT NULL
                         CHECK (stage IN ('immediate', 'next_day', 'one_week')),
    due_at       TEXT    NOT NULL,
    entry_id     INTEGER REFERENCES entries(id) ON DELETE SET NULL,  -- what they wrote
    completed_at TEXT,
    skipped_at   TEXT,
    created_at   TEXT    NOT NULL
);

-- One row per stage per anchor. Expressed as an index because SQLite does not allow
-- expressions inside an inline UNIQUE constraint, and either the event or the entry may
-- be the anchor (the calendar is optional).
CREATE UNIQUE INDEX IF NOT EXISTS idx_reflection_stage_unique
    ON reflection_stages (COALESCE(event_id, -1), COALESCE(anchor_entry_id, -1), stage);
CREATE INDEX IF NOT EXISTS idx_reflection_due
    ON reflection_stages (account_id, due_at, completed_at);

-- ---------------------------------------------------------------- cooldown

-- KRYteria Cooldown: reflection that has stopped producing anything is rumination, and
-- the product should say so rather than keep selling turns.
--
-- IMPORTANT: distress is never treated as evidence that the user is deciding badly. The
-- cooldown exists to stop endless analysis masquerading as progress, not to suppress
-- feelings or to imply the user is being irrational.
CREATE TABLE IF NOT EXISTS cooldown_state (
    id            INTEGER PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    topic_key     TEXT    NOT NULL,              -- what is being revisited
    visits        INTEGER NOT NULL DEFAULT 1,
    new_evidence_since_last INTEGER NOT NULL DEFAULT 0,
    last_visit_at TEXT    NOT NULL,
    resting_until TEXT,                          -- user-chosen interval, never imposed
    summary_known TEXT,                          -- what is known
    summary_unknown TEXT,                        -- what remains unknown
    summary_would_help TEXT,                     -- what new information would change it
    created_at    TEXT    NOT NULL,
    UNIQUE (account_id, topic_key)
);

-- ---------------------------------------------------------------- reconciliation

-- Perspective Reconciliation: what the user feels right now, set beside what the record
-- actually holds. The purpose is symmetrical and must stay that way — stopping one
-- frustrating Tuesday from erasing six weeks of evidence, AND stopping six weeks of good
-- evidence from talking somebody out of a legitimate concern.
--
-- It reconciles. It does not resolve. Nothing here recommends staying or leaving.
CREATE TABLE IF NOT EXISTS reconciliations (
    id            INTEGER PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    entry_id      INTEGER REFERENCES entries(id) ON DELETE CASCADE,
    profile_id    INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
    person_id     INTEGER REFERENCES people(id) ON DELETE SET NULL,
    current_feeling TEXT  NOT NULL,              -- what this entry expresses
    broader_evidence TEXT NOT NULL,              -- what the accumulated record holds
    criterion_id  INTEGER REFERENCES criteria(id) ON DELETE SET NULL,
    tension       TEXT,                          -- why they appear to pull apart
    run_id        INTEGER,
    created_at    TEXT    NOT NULL
);

-- ---------------------------------------------------------------- evidence interrogation

-- Evidence Interrogation: interrogation of the CLAIM, never of the user.
--
-- "He's always late" → how often, over what period, by how much, was it communicated?
-- And it cuts both ways: "he really cares because he bought me dinner" gets the same
-- scrutiny. A positive interpretation does not get a free pass.
--
-- `materiality` is the brake. The agent asks only where the missing information would
-- actually change the assessment — nobody decompressing after a date should face a
-- forty-seven-question deposition.
CREATE TABLE IF NOT EXISTS interrogations (
    id            INTEGER PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    entry_id      INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    claim         TEXT    NOT NULL,              -- the user's words, quoted
    claim_valence TEXT    NOT NULL DEFAULT 'negative'
                          CHECK (claim_valence IN ('negative', 'positive', 'neutral')),
    gap_kind      TEXT    NOT NULL
                          CHECK (gap_kind IN ('frequency', 'pattern', 'magnitude',
                                              'communication', 'circumstances',
                                              'accountability', 'impact', 'definition',
                                              'comparison')),
    question      TEXT    NOT NULL,
    materiality   TEXT    NOT NULL DEFAULT 'material'
                          CHECK (materiality IN ('material', 'optional')),
    answer        TEXT,
    asked_at      TEXT    NOT NULL,
    answered_at   TEXT,
    declined_at   TEXT,                          -- the user may always decline
    run_id        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_interrogations_entry
    ON interrogations (account_id, entry_id);

-- ---------------------------------------------------------------- research layer

-- A curated knowledge base, seeded from data/research/. Findings INFORM possible
-- behavioural indicators; they never become deterministic rules. Nothing in this table
-- may be used to diagnose a person, assign them a type, or decide an assessment.
--
-- `verified_at` IS THE LOAD-BEARING COLUMN. A row is invisible to the agents until a
-- human has opened the source, confirmed the finding is characterised fairly, and
-- recorded the URL. `list_research_notes` filters unverified rows out by default and
-- `link_evidence` refuses a research_ref that does not resolve to a verified row — so a
-- citation the agent produces must correspond to something somebody actually checked.
--
-- That is the whole defence against a fabricated citation, which for this product would
-- be worse than having no research layer at all.
CREATE TABLE IF NOT EXISTS research_notes (
    id          INTEGER PRIMARY KEY,
    ref         TEXT    NOT NULL UNIQUE,         -- stable id the agent cites, e.g. 'gottman-bids'
    area        TEXT    NOT NULL,                -- attachment | emotional_regulation | ...
    concept     TEXT,
    finding     TEXT    NOT NULL,                -- what the literature reports
    attribution TEXT,
    citation    TEXT    NOT NULL,                -- so the user can see why
    -- How well the bibliography settled when it was looked up, and what it rests on.
    -- Surfaced by the verification tool so nobody promotes an entry whose page range was
    -- never actually confirmed.
    citation_confidence TEXT,
    citation_checked_against TEXT,
    source_url  TEXT,                            -- what the verifier actually opened
    caveat      TEXT    NOT NULL,                -- the limits of applying it to one person
    do_not_json TEXT    NOT NULL DEFAULT '[]',   -- the misuse this finding invites
    indicator_hints_json TEXT NOT NULL DEFAULT '[]',
    -- True for findings that may only inform how the safety layer DESCRIBES a behaviour.
    -- Never a checklist item, never an assessment, never a label for a person.
    safety_adjacent INTEGER NOT NULL DEFAULT 0,
    verified_at TEXT,                            -- NULL = pending = invisible to agents
    verified_by TEXT,
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_area ON research_notes (area, verified_at);

-- ---------------------------------------------------------------- patterns

CREATE TABLE IF NOT EXISTS patterns (
    id             INTEGER PRIMARY KEY,
    account_id     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    -- A finding is interpreted within one profile, for the same reason an evidence link
    -- is: the same behaviour reads differently depending on what the user is looking for.
    -- Nullable because a finding can be about the user's own decisions rather than about
    -- one objective.
    profile_id     INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
    domain_id      INTEGER REFERENCES domains(id) ON DELETE CASCADE,
    kind           TEXT    NOT NULL
                           CHECK (kind IN ('recurring_unmet_need', 'repeated_discrepancy',
                                           'shifting_expectation', 'stated_vs_chosen',
                                           'insufficient_evidence')),
    statement      TEXT    NOT NULL,            -- neutral description, never a verdict
    criterion_id   INTEGER REFERENCES criteria(id) ON DELETE SET NULL,
    support_count  INTEGER NOT NULL DEFAULT 0,  -- how many entries back it. Shown to the user.
    contra_count   INTEGER NOT NULL DEFAULT 0,  -- how many entries cut against it
    -- Qualitative only. There is deliberately no numeric score column anywhere in this
    -- schema: not for a pattern, not for a person, not for a relationship.
    evidence_strength TEXT NOT NULL
                           CHECK (evidence_strength IN ('insufficient', 'limited',
                                                        'moderate', 'strong')),
    gap_note       TEXT,                        -- what is missing, when evidence is thin
    uncertainties_json TEXT NOT NULL DEFAULT '[]',
    -- Required, not optional. A finding that admits no other reading is a verdict wearing
    -- a finding's clothes, and this product does not issue verdicts.
    alternatives_json  TEXT NOT NULL DEFAULT '[]',
    status         TEXT    NOT NULL DEFAULT 'open'
                           CHECK (status IN ('open', 'addressed', 'dismissed')),
    run_id         INTEGER,
    created_at     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patterns_account
    ON patterns (account_id, domain_id, status);

-- Every finding must reference its supporting journal entries. PRD section D.
-- A pattern with no rows here is invalid and store.py refuses to write it.
--
-- `stance` is why this is a table and not a list of ids: counter-evidence is preserved
-- alongside the evidence, as a first-class row. An app that only stores what agrees with
-- its own finding is building a case, not holding up a mirror.
CREATE TABLE IF NOT EXISTS pattern_evidence (
    pattern_id     INTEGER NOT NULL REFERENCES patterns(id) ON DELETE CASCADE,
    entry_id       INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    observation_id INTEGER REFERENCES observations(id) ON DELETE SET NULL,
    stance         TEXT    NOT NULL DEFAULT 'supports'
                           CHECK (stance IN ('supports', 'contradicts')),
    PRIMARY KEY (pattern_id, entry_id, observation_id)
);

-- ---------------------------------------------------------------- reflection + decisions

CREATE TABLE IF NOT EXISTS reflections (
    id         INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    pattern_id INTEGER REFERENCES patterns(id) ON DELETE CASCADE,
    question   TEXT    NOT NULL,
    context    TEXT,                            -- the "let's examine the discrepancy" framing
    tone_mode  TEXT    NOT NULL
    -- Must match accounts.tone_mode and store.TONE_MODES. This was left on the old
    -- gentle/direct/no_bs values when the triad became Clarity/Tough Love, and the
    -- column-drift guard cannot see a changed CHECK — so any constraint duplicated
    -- across tables needs changing in both places by hand.
                       CHECK (tone_mode IN ('clarity', 'tough_love')),
    is_postponement_probe INTEGER NOT NULL DEFAULT 0,  -- the signature question
    run_id     INTEGER,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id            INTEGER PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    reflection_id INTEGER REFERENCES reflections(id) ON DELETE SET NULL,
    pattern_id    INTEGER REFERENCES patterns(id) ON DELETE SET NULL,
    criterion_id  INTEGER REFERENCES criteria(id) ON DELETE SET NULL,
    choice        TEXT    NOT NULL
                          CHECK (choice IN ('talk', 'boundary', 'more_time', 'gather_info',
                                            'reconsider', 'revise_criterion', 'undecided')),
    action_text   TEXT,                         -- what the user said they would do
    revisit_on    TEXT,                         -- only if the user asked to be reminded
    outcome       TEXT    NOT NULL DEFAULT 'open'
                          CHECK (outcome IN ('open', 'did_it', 'did_not', 'no_longer_relevant')),
    outcome_note  TEXT,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_account
    ON decisions (account_id, created_at DESC);
-- Repeated postponement is the differentiator; make counting it cheap.
CREATE INDEX IF NOT EXISTS idx_decisions_postponed
    ON decisions (account_id, criterion_id, choice);

-- ---------------------------------------------------------------- agent execution log

CREATE TABLE IF NOT EXISTS agent_runs (
    id           INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    route        TEXT    NOT NULL,              -- which workflow the orchestrator chose
    status       TEXT    NOT NULL DEFAULT 'running'
                         CHECK (status IN ('running', 'ok', 'failed', 'refused',
                                           'budget_exceeded', 'safety_halt')),
    detail       TEXT,
    started_at   TEXT    NOT NULL,
    finished_at  TEXT
);

-- NOTHING IN THIS TABLE MAY CONTAIN RAW JOURNAL TEXT.
-- `note` is for status and error messages; `tool_calls_json` records tool NAMES and
-- argument KEYS, never argument values. The execution log is operational telemetry, it is
-- shown in the trace view, and it is the one place a user's private writing could leak
-- into something that looks safe to screenshot or paste into a report.
CREATE TABLE IF NOT EXISTS agent_steps (
    id                  INTEGER PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    seq                 INTEGER NOT NULL,
    agent               TEXT    NOT NULL,       -- criteria | evidence | pattern | reflection | safety
    model_name          TEXT,                   -- what actually billed, per step
    provider            TEXT,                   -- which provider served it
    prompt_version      TEXT,                   -- so a regression can be traced to a prompt
    tool_calls_json     TEXT    NOT NULL DEFAULT '[]',
    input_tokens        INTEGER NOT NULL DEFAULT 0,
    -- NULL means the provider did not report it. Deliberately nullable: recording an
    -- unknown as 0 would understate cache hits and overstate cost, and a tokenomics
    -- section built on that is wrong in a way nobody can see.
    cached_input_tokens INTEGER,
    output_tokens       INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd  REAL    NOT NULL DEFAULT 0.0,
    actual_cost_usd     REAL,                   -- NULL unless the provider reports one
    latency_ms          INTEGER NOT NULL DEFAULT 0,
    ok                  INTEGER NOT NULL DEFAULT 1,
    is_simulated        INTEGER NOT NULL DEFAULT 0,  -- demo mode; excluded from cost totals
    error_message       TEXT,
    note                TEXT,
    created_at          TEXT    NOT NULL,
    UNIQUE (run_id, seq)
);

-- ---------------------------------------------------------------- safety + budget

-- THE SAFETY LAYER IS INDEPENDENT OF PROFILES.
--
-- Note there is no profile_id column, and that is deliberate. A user must never have to
-- mark physical safety, consent, or freedom from coercion as a Mandatory criterion before
-- the app recognises a serious concern. This is the one documented exception to the
-- user-defined criteria framework, and it applies in every context — marriage, casual
-- dating, friends-with-benefits, a one-night encounter.
CREATE TABLE IF NOT EXISTS safety_events (
    id         INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    entry_id   INTEGER REFERENCES entries(id) ON DELETE SET NULL,
    run_id     INTEGER REFERENCES agent_runs(id) ON DELETE SET NULL,
    trigger    TEXT    NOT NULL,                -- what fired: risk_language | injection | ...
    -- Categories overlap, and abuse can be a pattern, a single serious incident, or both.
    category   TEXT
                       CHECK (category IN ('physical', 'emotional_psychological',
                                           'sexual', 'coercive_control',
                                           'stalking_harassment', 'self_harm',
                                           'not_applicable')),
    -- Four levels, because the response is proportionate. Treating a difficult feeling
    -- as an emergency is its own kind of failure: it teaches people that telling the app
    -- something hard makes it stop being able to talk to them.
    concern_level TEXT NOT NULL DEFAULT 'potential'
                       CHECK (concern_level IN ('potential', 'pattern', 'disclosure',
                                                'immediate_danger')),
    action     TEXT    NOT NULL,                -- halt_and_route | offer_resources | refuse | note_only
    detail     TEXT,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_safety_events_account
    ON safety_events (account_id, created_at DESC);

-- ---------------------------------------------------------------- resource directory

-- A curated directory. NOTHING MAY BE INVENTED — not a number, not a service, not an
-- availability claim. If a resource is not in this table, the agent does not have one to
-- offer, and says so rather than guessing. `verified_at` exists so staleness is visible.
CREATE TABLE IF NOT EXISTS resources (
    id           INTEGER PRIMARY KEY,
    region       TEXT    NOT NULL DEFAULT 'US',
    name         TEXT    NOT NULL,
    kind         TEXT    NOT NULL
                         CHECK (kind IN ('emergency', 'confidential_support', 'information')),
    categories   TEXT    NOT NULL DEFAULT '[]',  -- which concerns it serves
    phone        TEXT,
    text_line    TEXT,
    url          TEXT,
    hours        TEXT,
    note         TEXT,
    verified_at  TEXT    NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1
);

-- What was offered, and what the user said about it.
--
-- SUPPORT WITHOUT COERCION. A decline is recorded and respected: the agent does not keep
-- raising resources the user has already turned down. It does NOT turn the safety layer
-- off — a new disclosure of danger is still recognised and still answered.
CREATE TABLE IF NOT EXISTS resource_offers (
    id              INTEGER PRIMARY KEY,
    account_id      INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    safety_event_id INTEGER REFERENCES safety_events(id) ON DELETE SET NULL,
    resource_ids    TEXT    NOT NULL DEFAULT '[]',
    concern_level   TEXT    NOT NULL,
    response        TEXT    NOT NULL DEFAULT 'pending'
                            CHECK (response IN ('pending', 'accepted', 'declined',
                                                'ignored')),
    responded_at    TEXT,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_resource_offers
    ON resource_offers (account_id, created_at DESC);

-- Per-account daily caps. A hosted app spends money when strangers use it; this is enforced
-- in code by the orchestrator, never requested in a prompt.
CREATE TABLE IF NOT EXISTS usage_daily (
    account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    day          TEXT    NOT NULL,              -- YYYY-MM-DD, UTC
    calls        INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd     REAL    NOT NULL DEFAULT 0.0,
    PRIMARY KEY (account_id, day)
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
