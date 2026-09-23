// Mirrors the backend Pydantic schemas (app/schemas.py) and enums
// (app/models/enums.py). Kept in sync by hand.

// Free text, not a fixed set — these are offered as datalist suggestions for
// the common cases, but a program's own deadlines can call for anything.
export const DEADLINE_TYPES = [
  "application",
  "funding",
  "rec_letters_by",
  "test_scores_by",
  "other",
];

// Free text, not a fixed set — GRE/TOEFL/Application Fee/Fee Waiver/
// Recommendation Letters/Essay Type are the six built-in kinds every
// program is seeded with, but a program's own requirement can be labelled
// anything.

export type RequirementSource = "researched" | "confirmed_by_program";

export type Urgency = "overdue" | "due_soon" | "upcoming" | "none";

/** A requirement's current value, for a row that only shows it (Dashboard). */
export interface RequirementSnapshot {
  value: string | null;
  source: RequirementSource;
  needs_human_verification: boolean;
}

export interface ProgramSummary {
  id: number;
  university: string;
  department: string | null;
  degree: string | null;
  portal_url: string | null;
  date_added: string;
  application_deadline: string | null;
  faculty_count: number;
  sort_order: number;
  steps_completed: number;
  steps_total: number;
  days_until_deadline: number | null;
  urgency: Urgency;
  last_activity: string | null;
  is_stale: boolean;
  /** None when that requirement kind hasn't been recorded for this program. */
  gre: RequirementSnapshot | null;
  toefl: RequirementSnapshot | null;
  app_fee: RequirementSnapshot | null;
}

/** One dated thing on the Dashboard: a deadline row or a My Notes reminder. */
export interface AgendaItem {
  program_id: number;
  university: string;
  kind: "deadline" | "reminder";
  /** A deadline's free-text type, or the reminder note's text. */
  label: string;
  date: string;
  /** Null for a reminder — no Claude contract writes one. */
  source: RequirementSource | null;
  needs_human_verification: boolean;
}

export type AttentionKind =
  | "overdue"
  | "stale"
  | "no_deadline_date"
  | "missing_requirements"
  | "unverified";

export interface AttentionItem {
  program_id: number;
  university: string;
  kind: AttentionKind;
  detail: string;
  /** The program-detail tab that fixes it. */
  tab: "overview" | "faculty" | "docs" | "notes";
}

export interface ChecklistRow {
  program_id: number;
  university: string;
  /** Built-in step key -> done; null where the user deleted that step. */
  steps: Record<string, boolean | null>;
  custom_done: number;
  custom_total: number;
}

/** A requirement boiled down for the Dashboard's comparison table. */
export interface CompareCell {
  /** The short read ("Required · min 90", "$125"); null when nothing is recorded. */
  text: string | null;
  /** The full stored value, for hover. */
  detail: string | null;
  source: RequirementSource;
  needs_human_verification: boolean;
}

export interface CompareRow {
  program_id: number;
  gre: CompareCell;
  toefl: CompareCell;
  app_fee: CompareCell;
}

export interface DashboardOverview {
  programs: ProgramSummary[];
  submitted_count: number;
  unverified_count: number;
  agenda: AgendaItem[];
  attention: AttentionItem[];
  step_columns: { key: string; label: string }[];
  checklist: ChecklistRow[];
  compare: CompareRow[];
  fee_total: number;
  fee_counted: number;
  fee_unknown: number;
}

export interface Faculty {
  id: number;
  program_id: number;
  name: string;
  research_areas: string | null;
  homepage_url: string | null;
  contacted: boolean;
  /** Position in the user's manual ordering, set by dragging cards. */
  sort_order: number;
  /**
   * The researched profile: markdown sections whose every bullet cites the
   * sentence it came from. Rendered by the same `Notes` component as a
   * program's notes. Null until a research pass has been run for this person.
   */
  dossier: string | null;
  /** Which model wrote the dossier above — provenance, not today's config. */
  dossier_model: string | null;
  dossier_researched_at: string | null;
  notes: FacultyNote[];
}

/** A user-typed note about one faculty member. No Claude contract writes
 * these (unlike a program's notes), so there's no source/quote to track. */
export interface FacultyNote {
  id: number;
  faculty_id: number;
  text: string;
  sort_order: number;
}

export interface Deadline {
  id: number;
  program_id: number;
  type: string;
  // Null until the user fills one in — every program is seeded with an
  // Application deadline even when no date is known yet.
  date: string | null;
  notes: string | null;
  sort_order: number;
  source: RequirementSource;
  needs_human_verification: boolean;
}

export interface Requirement {
  id: number;
  program_id: number;
  kind: string;
  value: string | null;
  source: RequirementSource;
  needs_human_verification: boolean;
  sort_order: number;
}

/** One cited fact about a program, individually confirmable (Rule 8). */
export interface ProgramNote {
  id: number;
  program_id: number;
  text: string;
  // Null for a hand-added note, or legacy uncited prose -- also what keeps
  // it out of the verify badge (nothing to check without a quote).
  quote: string | null;
  source_url: string | null;
  source_label: string | null;
  source: RequirementSource;
  needs_human_verification: boolean;
  sort_order: number;
}

/** A user-typed note on the program's My Notes tab. Text may be empty when the
 * note is just a link, file or date — the backend requires at least one. */
export interface MyNote {
  id: number;
  program_id: number;
  text: string;
  link_url: string | null;
  due_date: string | null;
  file_name: string | null;
  sort_order: number;
}

export interface ProgramStep {
  id: number;
  program_id: number;
  key: string;
  label: string;
  completed: boolean;
  completed_at: string | null;
  sort_order: number;
  is_custom: boolean;
}

export interface ProgramDetail {
  id: number;
  university: string;
  department: string | null;
  degree: string | null;
  /** The department/program page. Where you *apply* is `application_url`. */
  portal_url: string | null;
  application_url: string | null;
  admissions_email: string | null;
  /** Null for a hand-added program, or one researched before this was tracked. */
  research_model: string | null;
  date_added: string;
  faculty: Faculty[];
  deadlines: Deadline[];
  requirements: Requirement[];
  notes: ProgramNote[];
  my_notes: MyNote[];
  steps: ProgramStep[];
}

export interface ProgramCreate {
  university: string;
  department?: string | null;
  degree?: string | null;
  portal_url?: string | null;
  application_url?: string | null;
  admissions_email?: string | null;
}

/** One uploaded file under a doc type — a plain list, newest first. */
export interface DocFile {
  id: number;
  doc_type_id: number;
  filename: string;
  created_at: string;
}

/** One slot in a program's "My Docs" tab: CV and Statement of Purpose are
 * built in; the user can add, rename, or delete any type, built-in or
 * custom. Independent per program — the same as Faculty. */
export interface DocType {
  id: number;
  program_id: number;
  key: string;
  title: string;
  is_custom: boolean;
  sort_order: number;
  files: DocFile[];
}

export interface SuggestedFaculty {
  name: string;
  research_areas: string | null;
  homepage_url: string | null;
}

export interface SuggestFacultyResult {
  faculty: SuggestedFaculty[];
  /** Found by the pass but already on the program's list, so not suggested. */
  already_listed: string[];
}
