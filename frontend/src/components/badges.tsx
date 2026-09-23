import { formatDate } from "../format";
import type { RequirementSource } from "../types";
import { Button } from "./ui";

// Words that are acronyms, not ordinary capitalised words.
const ACRONYMS: Record<string, string> = {
  gre: "GRE",
  gmat: "GMAT",
  toefl: "TOEFL",
  ielts: "IELTS",
  cv: "CV",
  sop: "SOP",
};

export function humanize(value: string): string {
  return value
    .split("_")
    .map((w) => ACRONYMS[w.toLowerCase()] ?? w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// Whole-phrase overrides for the requirement kinds where per-word
// humanize() reads oddly ("app_fee" -> "App Fee" instead of "Application
// Fee"). Anything not listed (a custom kind) falls back to humanize().
const REQUIREMENT_KIND_LABELS: Record<string, string> = {
  app_fee: "Application Fee",
  fee_waiver: "Fee Waiver",
  rec_letters: "Recommendation Letters",
  essay_type: "Essay Type",
};

export function humanizeRequirementKind(kind: string): string {
  return REQUIREMENT_KIND_LABELS[kind] ?? humanize(kind);
}

// ── Colour contract ──────────────────────────────────────────────────────
// Only three non-neutral colours:
//   red   — overdue, or due within 14 days
//   amber — needs verification, or due within 45 days
//   green — confirmed / positive terminal state
// Everything else is neutral.

/**
 * A deadline's colour follows the days left, on the same bands the backend's
 * urgency uses (insights.urgency_for: due_soon ≤ 14, upcoming ≤ 45) — so a
 * date turns amber, then red, as it approaches, and stays red once it's past,
 * which is also when the Programs list marks the program overdue.
 */
function deadlineInfo(date: string) {
  const days = Math.ceil(
    (new Date(date + "T00:00:00").getTime() - Date.now()) / 86_400_000,
  );
  let color = "text-ink-subtle";
  if (days <= 14) color = "text-danger";
  else if (days <= 45) color = "text-warning";
  const label = days < 0 ? `${-days}d ago` : days === 0 ? "today" : `${days}d`;
  return { color, label };
}

/** Deadline as plain text — coloured only when it actually needs attention. */
export function DeadlineBadge({ date }: { date: string | null }) {
  if (!date) return <span className="text-xs text-ink-faint">No date</span>;

  const { color, label } = deadlineInfo(date);
  return (
    <span className={`whitespace-nowrap text-xs tabular-nums ${color}`}>
      {formatDate(date)} <span className="opacity-60">· {label}</span>
    </span>
  );
}

/**
 * Same data as DeadlineBadge, but the date and days-left sit in a fixed-width
 * row split by `justify-between` instead of running together — so across a
 * list of many rows, every date and every day-count lines up in its own
 * column instead of drifting with each row's other content.
 */
export function DeadlineColumn({ date }: { date: string | null }) {
  if (!date) {
    return (
      <span className="flex w-40 shrink-0 text-sm text-ink-faint">No date</span>
    );
  }

  const { color, label } = deadlineInfo(date);
  return (
    <span className={`flex w-40 shrink-0 items-baseline justify-between text-sm tabular-nums ${color}`}>
      <span>{formatDate(date)}</span>
      <span className="opacity-60">{label}</span>
    </span>
  );
}

/** Rule 8: distinguish researched guesses from program-confirmed facts. */
export function SourceBadge({
  source,
  needsVerification,
}: {
  source: RequirementSource;
  needsVerification: boolean;
}) {
  const confirmed = source === "confirmed_by_program";
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
        confirmed ? "bg-success-surface text-success" : "bg-warning-surface text-warning"
      }`}
      title={
        confirmed
          ? "Confirmed by the program"
          : needsVerification
            ? "Researched — needs human verification before you rely on it"
            : "Researched — verify before relying on it"
      }
    >
      {confirmed ? "confirmed" : needsVerification ? "verify" : "researched"}
    </span>
  );
}

/**
 * A researched fact's provenance badge plus the button that promotes it to
 * confirmed — the same pair on every deadline, requirement and note, so a
 * fact is verified the same way wherever it sits.
 */
export function ConfirmFact({
  source,
  needsVerification,
  disabled,
  onConfirm,
}: {
  source: RequirementSource;
  needsVerification: boolean;
  disabled?: boolean;
  onConfirm: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center gap-2">
      <SourceBadge source={source} needsVerification={needsVerification} />
      <Button
        variant="ghost"
        title="Mark confirmed by the program"
        disabled={disabled}
        onClick={onConfirm}
      >
        Confirm
      </Button>
    </div>
  );
}
