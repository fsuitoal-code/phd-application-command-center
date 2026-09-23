import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../api";
import { DeadlineBadge, DeadlineColumn, SourceBadge, humanize } from "../components/badges";
import {
  EmptyState,
  ErrorText,
  List,
  Loading,
  Panel,
  TextButton,
  eyebrow,
  focusRing,
} from "../components/ui";
import { errorText, programName } from "../format";
import { useTitle } from "../hooks/useTitle";
import type {
  AgendaItem,
  AttentionItem,
  AttentionKind,
  ChecklistRow,
  DashboardOverview,
  CompareCell,
  CompareRow,
  ProgramSummary,
} from "../types";

/**
 * Dashboard — the page you open first. Where the Programs page answers
 * "what am I applying to?", this answers "what's next?" (a date-ordered agenda
 * across every program), "what's slipping?" (each problem with its reason and
 * the tab that fixes it), and only then "how do they compare?". Read-only: the
 * agenda and attention list are ordered by date and severity, never dragged.
 */
export default function Dashboard() {
  useTitle("Dashboard");
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .dashboardOverview()
      .then(setData)
      .catch((e) => setError(errorText(e)));
  }, []);

  const names = data ? namesOf(data) : new Map<number, string>();

  return (
    <>
      <header className="mb-6">
        <h1 className="font-display text-xl font-semibold tracking-tight">Dashboard</h1>
      </header>

      {error && <ErrorText>{error}</ErrorText>}

      {data === null && !error && <Loading />}

      {data && data.programs.length === 0 && (
        <EmptyState>No programs yet — add one from the Programs page.</EmptyState>
      )}

      {data && data.programs.length > 0 && (
        <div className="space-y-6">
          <Stats data={data} />
          <div className="grid items-start gap-6 lg:grid-cols-5">
            <div className="min-w-0 lg:col-span-3">
              <Upcoming items={data.agenda} names={names} />
            </div>
            <div className="min-w-0 lg:col-span-2">
              <Attention items={data.attention} names={names} />
            </div>
          </div>
          <Checklist data={data} names={names} />
          <Comparison data={data} />
        </div>
      )}
    </>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────

/** Whole days from today to a date-only value — same arithmetic as the
 * deadline badges, so a row's group and its "3d" label never disagree. */
function daysUntil(date: string): number {
  return Math.ceil((new Date(date + "T00:00:00").getTime() - Date.now()) / 86_400_000);
}

function programHref(id: number, tab?: string) {
  return tab && tab !== "overview" ? `/programs/${id}?tab=${tab}` : `/programs/${id}`;
}

/** Program id -> its short name ("PhD Industrial Engineering"). Rows carry the
 * university, but two programs can share one, so every row names both. */
type Names = Map<number, string>;

function namesOf(data: DashboardOverview): Names {
  return new Map(data.programs.map((p) => [p.id, programName(p.degree, p.department)]));
}

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}

/** The small-caps tag used for a neutral label beside a row (e.g. "reminder"). */
const tag =
  "rounded bg-surface-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-subtle";

// ── Stats ────────────────────────────────────────────────────────────────

function Stats({ data }: { data: DashboardOverview }) {
  const next = data.agenda.find((a) => a.kind === "deadline" && daysUntil(a.date) >= 0);
  const attentionPrograms = new Set(data.attention.map((a) => a.program_id)).size;
  const overdue = data.attention.filter((a) => a.kind === "overdue").length;
  const stale = data.attention.filter((a) => a.kind === "stale").length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat label="Programs" value={data.programs.length}>
        {plural(data.submitted_count, "application")} submitted
      </Stat>
      <Stat
        label="Next deadline"
        wrap
        value={
          next ? (
            <Link
              to={programHref(next.program_id)}
              // A name, not a number: set a size down so it fits in full.
              className={`block rounded text-base leading-snug hover:underline ${focusRing}`}
            >
              {next.university}
            </Link>
          ) : (
            "—"
          )
        }
      >
        {next ? (
          <>
            {humanize(next.label)} · <DeadlineBadge date={next.date} />
          </>
        ) : (
          "No dated deadlines"
        )}
      </Stat>
      <Stat
        label="Need attention"
        value={attentionPrograms}
        unit={attentionPrograms === 1 ? "program" : "programs"}
      >
        {overdue > 0 || stale > 0 ? (
          <>
            {overdue > 0 && <span className="text-danger">{overdue} overdue</span>}
            {overdue > 0 && stale > 0 && " · "}
            {stale > 0 && <span className="text-warning">{stale} stale</span>}
          </>
        ) : attentionPrograms > 0 ? (
          "With open issues"
        ) : (
          "All clear"
        )}
      </Stat>
      {/* Counts stay neutral: colour marks one item's status (a date, an
          overdue/stale count), never a running total that's rarely zero. */}
      <Stat label="Unverified facts" value={data.unverified_count}>
        Researched, not confirmed
      </Stat>
    </div>
  );
}

function Stat({
  label,
  value,
  unit,
  wrap,
  children,
}: {
  label: string;
  value: React.ReactNode;
  /** What the number counts, set small beside it, when the label doesn't say. */
  unit?: string;
  /** Let the value wrap instead of truncating — for a name that must read in full. */
  wrap?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-hairline bg-surface px-4 py-3">
      <div className={eyebrow}>{label}</div>
      <div
        className={`mt-1 ${wrap ? "break-words" : "truncate"} font-display text-xl font-semibold tabular-nums tracking-tight text-ink`}
      >
        {value}
        {unit && (
          <span className="ml-1.5 font-sans text-sm font-normal tracking-normal text-ink-subtle">
            {unit}
          </span>
        )}
      </div>
      <div className="mt-0.5 truncate text-xs text-ink-subtle">{children}</div>
    </div>
  );
}

// ── Upcoming ─────────────────────────────────────────────────────────────

const GROUPS: { id: string; label: string; test: (days: number) => boolean }[] = [
  { id: "overdue", label: "Overdue", test: (d) => d < 0 },
  { id: "week", label: "Next 7 days", test: (d) => d >= 0 && d <= 7 },
  { id: "month", label: "Next 30 days", test: (d) => d > 7 && d <= 30 },
  { id: "later", label: "Later", test: (d) => d > 30 },
];

function Upcoming({ items, names }: { items: AgendaItem[]; names: Names }) {
  // Everything past a month out is kept one click away, so the near term
  // reads first.
  const [showLater, setShowLater] = useState(false);

  return (
    <Panel
      title={
        <>
          Upcoming
          <span className="text-xs font-normal text-ink-faint">
            Deadlines and My Notes reminders, soonest first
          </span>
        </>
      }
    >
      {items.length === 0 ? (
        <EmptyState>No dated deadlines or reminders yet.</EmptyState>
      ) : (
        GROUPS.map((g) => {
          const rows = items.filter((a) => g.test(daysUntil(a.date)));
          if (rows.length === 0) return null;
          const collapsed = g.id === "later" && !showLater;
          return (
            <div key={g.id} className="py-2">
              <div className={`${eyebrow} flex items-center gap-2 pt-1`}>
                {g.label}
                <span className="font-normal tabular-nums text-ink-faint">{rows.length}</span>
                {g.id === "later" && (
                  <TextButton onClick={() => setShowLater(!showLater)} className="ml-auto normal-case tracking-normal">
                    {showLater ? "Hide" : "Show"}
                  </TextButton>
                )}
              </div>
              {!collapsed && (
                <List>
                  {rows.map((a, i) => (
                    <AgendaRow
                      key={`${a.kind}-${a.program_id}-${a.date}-${i}`}
                      item={a}
                      name={names.get(a.program_id)}
                    />
                  ))}
                </List>
              )}
            </div>
          );
        })
      )}
    </Panel>
  );
}

function AgendaRow({ item, name }: { item: AgendaItem; name?: string }) {
  const reminder = item.kind === "reminder";
  return (
    // The whole row is the link (the Link's after:inset-0 overlay), the same
    // one-click-target treatment as a row on the Programs page.
    <li className="group relative flex flex-col gap-1 py-2.5 sm:flex-row sm:items-center sm:gap-4">
      <DeadlineColumn date={item.date} />
      <div className="min-w-0 flex-1">
        <Link
          to={programHref(item.program_id, reminder ? "notes" : "overview")}
          className={`block truncate rounded text-sm text-ink after:absolute after:inset-0 group-hover:underline ${focusRing}`}
          title={item.label}
        >
          {reminder ? item.label : humanize(item.label)}
        </Link>
        <div className="truncate text-xs text-ink-subtle">
          {item.university}
          {name && name !== "—" && <span className="text-ink-faint"> · {name}</span>}
        </div>
      </div>
      <div className="shrink-0">
        {reminder ? (
          <span className={tag}>reminder</span>
        ) : (
          item.source &&
          item.source !== "confirmed_by_program" && (
            <SourceBadge
              source={item.source}
              needsVerification={item.needs_human_verification}
            />
          )
        )}
      </div>
    </li>
  );
}

// ── Needs attention ──────────────────────────────────────────────────────

/** Colour contract: red for overdue, amber for anything needing a look. */
const DOT: Record<AttentionKind, string> = {
  overdue: "bg-danger-solid",
  stale: "bg-warning-solid",
  no_deadline_date: "bg-warning-solid",
  missing_requirements: "bg-warning-solid",
  unverified: "bg-warning-solid",
};

const TAB_LABEL: Record<AttentionItem["tab"], string> = {
  overview: "Overview",
  faculty: "Faculty",
  docs: "My Docs",
  notes: "My Notes",
};

function Attention({ items, names }: { items: AttentionItem[]; names: Names }) {
  // One row per program, its issues listed under it. Items arrive most
  // pressing first (then in Programs-page order), so grouping by first
  // appearance puts the program with the worst issue on top, and each
  // program's own issues stay in severity order.
  const groups = new Map<number, AttentionItem[]>();
  for (const a of items) groups.set(a.program_id, [...(groups.get(a.program_id) ?? []), a]);

  return (
    <Panel
      title={
        <>
          Needs attention
          {groups.size > 0 && (
            <span className="text-xs font-normal tabular-nums text-ink-faint">
              {groups.size}
            </span>
          )}
        </>
      }
    >
      {groups.size === 0 ? (
        <EmptyState>Nothing needs attention.</EmptyState>
      ) : (
        <List>
          {[...groups.values()].map((issues) => {
            const first = issues[0];
            return (
              <li key={first.program_id} className="group relative py-2.5">
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    {/* The whole row opens the tab that fixes its most
                        pressing issue. */}
                    <Link
                      to={programHref(first.program_id, first.tab)}
                      className={`block truncate rounded text-sm font-medium text-ink after:absolute after:inset-0 group-hover:underline ${focusRing}`}
                    >
                      {first.university}
                    </Link>
                    <div className="truncate text-xs text-ink-faint">
                      {names.get(first.program_id)}
                    </div>
                  </div>
                  <span className="shrink-0 pt-0.5 text-xs text-ink-faint">
                    {TAB_LABEL[first.tab]} →
                  </span>
                </div>
                <ul className="mt-1 space-y-0.5">
                  {issues.map((a) => (
                    <li key={a.kind} className="flex items-start gap-2 text-xs text-ink-subtle">
                      <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${DOT[a.kind]}`} />
                      <span className="min-w-0 break-words">{a.detail}</span>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </List>
      )}
    </Panel>
  );
}

// ── Checklist grid ───────────────────────────────────────────────────────

/** Column heads: each built-in step's own label (BUILTIN_STEPS), abbreviated
 * only as far as eight columns need. The full label is on hover. */
const SHORT_STEP: Record<string, string> = {
  requirements: "Researched reqs",
  deadlines: "Researched deadlines",
  faculty: "Researched faculty",
  faculty_outreach: "Reach out",
  sop: "Essays",
  cv: "Polish CV",
  submitted: "Submit app",
};

function Checklist({ data, names }: { data: DashboardOverview; names: Names }) {
  const cols = data.step_columns;
  const hasCustom = data.checklist.some((r) => r.custom_total > 0);
  // One template for the heading, body and footer rows, so columns can't drift.
  const template = {
    gridTemplateColumns: `minmax(8rem, 1.6fr) repeat(${cols.length + (hasCustom ? 1 : 0)}, minmax(4.5rem, 1fr))`,
  };
  const row = "grid items-center gap-2 px-4";

  return (
    <Panel
      title={
        <>
          Checklist
          <span className="text-xs font-normal text-ink-faint">
            Which step is behind across programs
          </span>
        </>
      }
    >
      {/* Too many columns for a phone: the grid scrolls sideways inside the
          panel rather than the page. -mx-4 lets it run to the panel's edges. */}
      <div className="-mx-4 -my-1 overflow-x-auto">
        <div className="min-w-[48rem]">
          <div className={`${row} border-b border-hairline py-2 ${eyebrow}`} style={template}>
            <span>Program</span>
            {cols.map((c) => (
              <span key={c.key} className="text-center leading-tight" title={c.label}>
                {SHORT_STEP[c.key] ?? c.label}
              </span>
            ))}
            {hasCustom && <span className="text-center" title="Steps you added yourself">Other</span>}
          </div>
          <ul className="divide-y divide-hairline-soft">
            {data.checklist.map((r) => (
              <ChecklistLine
                key={r.program_id}
                row={r}
                name={names.get(r.program_id)}
                cols={cols}
                hasCustom={hasCustom}
                className={row}
                style={template}
              />
            ))}
          </ul>
          <div
            className={`${row} border-t border-hairline py-2 text-xs tabular-nums text-ink-subtle`}
            style={template}
          >
            <span>Done</span>
            {cols.map((c) => {
              const present = data.checklist.filter((r) => r.steps[c.key] != null);
              const done = present.filter((r) => r.steps[c.key]).length;
              return (
                <span key={c.key} className="text-center">
                  {present.length ? `${done}/${present.length}` : "—"}
                </span>
              );
            })}
            {hasCustom && <span />}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function ChecklistLine({
  row: r,
  name,
  cols,
  hasCustom,
  className,
  style,
}: {
  row: ChecklistRow;
  name?: string;
  cols: { key: string; label: string }[];
  hasCustom: boolean;
  className: string;
  style: React.CSSProperties;
}) {
  return (
    <li className={`${className} py-2`} style={style}>
      <div className="min-w-0">
        <Link
          to={programHref(r.program_id)}
          className={`block truncate rounded text-sm text-ink hover:underline ${focusRing}`}
          title={r.university}
        >
          {r.university}
        </Link>
        <div className="truncate text-xs text-ink-faint" title={name}>
          {name}
        </div>
      </div>
      {cols.map((c) => (
        <StepCell key={c.key} done={r.steps[c.key]} label={`${c.label} — ${r.university}`} />
      ))}
      {hasCustom && (
        <span className="text-center text-xs tabular-nums text-ink-subtle">
          {r.custom_total ? `${r.custom_done}/${r.custom_total}` : <span className="text-ink-faint">—</span>}
        </span>
      )}
    </li>
  );
}

function StepCell({ done, label }: { done: boolean | null | undefined; label: string }) {
  if (done == null) {
    return (
      <span className="text-center text-sm text-ink-faint" title={`${label}: step removed`}>
        —
      </span>
    );
  }
  return (
    <span className="flex justify-center" title={`${label}: ${done ? "done" : "not done"}`}>
      {done ? (
        <span className="text-sm text-success" aria-label="done">
          ✓
        </span>
      ) : (
        <span className="h-2 w-2 rounded-full border border-hairline-strong" aria-label="not done" />
      )}
    </span>
  );
}

// ── Comparison ───────────────────────────────────────────────────────────

const COMPARE =
  "grid grid-cols-[minmax(0,1.6fr)_minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.8fr)] items-center gap-3 px-4";

function Comparison({ data }: { data: DashboardOverview }) {
  const fees =
    data.fee_counted > 0
      ? `~$${Math.round(data.fee_total).toLocaleString()} in application fees across ${plural(data.fee_counted, "program")}`
      : "No application fees recorded yet";
  const unknown = data.fee_unknown > 0 ? ` · ${data.fee_unknown} unknown or not in $` : "";
  const cells = new Map(data.compare.map((c) => [c.program_id, c]));

  return (
    <Panel
      title={
        <>
          Compare
          <span className="text-xs font-normal text-ink-faint">
            In your Programs-page order · hover a value for the full text
          </span>
        </>
      }
      footer={
        <p className="text-xs text-ink-subtle">
          {fees}
          <span className="text-ink-faint">{unknown}</span>
        </p>
      }
    >
      <div className="-mx-4 -my-1 overflow-x-auto">
        <div className="min-w-[40rem]">
          <div className={`${COMPARE} border-b border-hairline py-2 ${eyebrow}`}>
            <span>Program</span>
            <span>App deadline</span>
            <span>GRE</span>
            <span>TOEFL</span>
            <span>App fee</span>
          </div>
          <ul className="divide-y divide-hairline-soft">
            {data.programs.map((p) => (
              <ComparisonRow key={p.id} p={p} row={cells.get(p.id)} />
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}

function ComparisonRow({ p, row }: { p: ProgramSummary; row?: CompareRow }) {
  return (
    <li className={`${COMPARE} py-2.5`}>
      <div className="min-w-0">
        <Link
          to={programHref(p.id)}
          className={`block truncate rounded text-sm font-medium text-ink hover:underline ${focusRing}`}
        >
          {p.university}
        </Link>
        <div className="truncate text-xs text-ink-subtle" title={programName(p.degree, p.department)}>
          {programName(p.degree, p.department)}
        </div>
      </div>
      {/* The Application-type deadline only — funding and other deadlines
          are in Upcoming. */}
      <DeadlineBadge date={p.application_deadline} />
      <CompareValue cell={row?.gre} />
      <CompareValue cell={row?.toefl} />
      <CompareValue cell={row?.app_fee} />
    </li>
  );
}

/**
 * A requirement as a quick read ("Required · min 90", "$125") with the stored
 * sentence on hover, plus the same provenance badge the program's
 * Requirements panel shows until the fact is confirmed.
 */
function CompareValue({ cell }: { cell?: CompareCell }) {
  if (!cell?.text) {
    return <span className="text-sm text-ink-faint">—</span>;
  }
  const unread = cell.text === "See details";
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-1.5">
      <span
        className={`min-w-0 max-w-full truncate text-sm ${unread ? "text-ink-subtle" : "text-ink"}`}
        title={cell.detail ?? undefined}
      >
        {cell.text}
      </span>
      {cell.source !== "confirmed_by_program" && (
        <SourceBadge source={cell.source} needsVerification={cell.needs_human_verification} />
      )}
    </div>
  );
}
