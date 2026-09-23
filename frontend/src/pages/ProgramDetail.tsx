import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { api } from "../api";
import { useElementHeight } from "../hooks/useElementHeight";
import { ProgressSteps } from "../components/ProgressSteps";
import {
  Button,
  ErrorText,
  ExternalLink,
  Field,
  Loading,
  Tabs,
  TextButton,
  focusRing,
  input,
  pill,
  type Tab,
} from "../components/ui";
import { errorText } from "../format";
import { useTitle } from "../hooks/useTitle";
import NotFound from "./NotFound";
import type { ProgramDetail as Detail } from "../types";
import { OverviewTab } from "./program/OverviewTab";
import { FacultyTab } from "./program/FacultyTab";
import { MyDocsTab } from "./program/MyDocsTab";
import { MyNotesTab } from "./program/MyNotesTab";

type TabId = "overview" | "faculty" | "docs" | "notes";
const TAB_IDS: TabId[] = ["overview", "faculty", "docs", "notes"];

// Same shape as the link pill, but flags something the user hasn't supplied yet —
// the colour contract's "needs your attention" amber, not an error state.
const missingPill =
  "rounded-md border border-warning/40 bg-warning-surface px-2.5 py-1 text-xs text-warning transition-colors hover:border-warning";

export default function ProgramDetail() {
  const { id } = useParams();
  const pid = Number(id);
  const [p, setP] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // `?tab=notes` opens on that tab — how the Dashboard links straight to the
  // place that fixes what it flagged. Only the starting tab; switching tabs
  // afterwards doesn't rewrite the URL.
  const [params] = useSearchParams();
  const requested = params.get("tab") as TabId | null;
  const [tab, setTab] = useState<TabId>(
    requested && TAB_IDS.includes(requested) ? requested : "overview",
  );
  // The only editor a program has: a researched program has no other way to
  // correct what Claude got wrong, or to record where it is actually applied to.
  const [editing, setEditing] = useState(false);
  useTitle(p?.university ?? null);

  // This block's own rendered height, so a tab further down (a faculty card's
  // name row, pinned while its dossier scrolls) knows how far below the global
  // header it needs to sit — same reasoning as Layout's `--header-h`, one level
  // deeper. Zero whenever the block isn't actually pinned (a phone, or while
  // editing — see below), so nothing leaves a gap for it. Redone whenever the
  // block's content can change height, and on a resize across the breakpoint.
  const [stickyRef, stickyH] = useElementHeight<HTMLDivElement>(p, editing);
  useEffect(() => {
    const el = stickyRef.current;
    const apply = () => {
      const pinned = el && getComputedStyle(el).position === "sticky";
      document.documentElement.style.setProperty(
        "--program-header-h",
        `${pinned ? el.offsetHeight : 0}px`,
      );
    };
    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, [stickyRef, stickyH, editing]);

  async function reload() {
    try {
      setP(await api.getProgram(pid));
    } catch (e) {
      setError(errorText(e));
    }
  }
  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  if (error) return <NotFound message={`This program couldn't be loaded: ${error}`} />;
  if (!p) return <Loading />;

  const tabProps = { p, pid, reload };

  const tabs: Tab<TabId>[] = [
    { id: "overview", label: "Overview" },
    { id: "faculty", label: "Faculty" },
    { id: "docs", label: "My Docs" },
    { id: "notes", label: "My Notes" },
  ];

  return (
    <>
      {/* One sticky unit, not three independently-stuck ones: each element
          sticking on its own would lock at a different scroll offset (its
          own natural, pre-scroll position), leaving a gap that briefly
          exposed the tab content scrolling past underneath. Grouping them
          means the whole block engages and releases as a single rigid
          piece — nothing can slide relative to anything else.

          Pinned from `sm` up only: on a phone the block is ~370px, near half
          the screen, and pinning it would leave the tab content a sliver.
          Never pinned while editing either — the form inside can be taller
          than a short window, and a pinned block can't scroll to its Save. */}
      <div
        ref={stickyRef}
        className={`${editing ? "" : "sm:sticky"} z-[5] -mt-8 border-b border-hairline bg-canvas`}
        style={{ top: "var(--header-h, 64px)" }}
      >
        <header className="pb-3 pt-3">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
            <div className="min-w-0">
              <h1 className="font-display text-xl font-semibold tracking-tight">
                {p.university}
              </h1>
              <p className="text-xs text-ink-subtle">
                {[p.department, p.degree].filter(Boolean).join(" · ") || "—"}
              </p>
            </div>
            {/* The header's job is quick access to this program's own pages —
                nothing else. Status lives with the progress it describes, and
                the deadline is already said twice below. */}
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              {p.portal_url && <ExternalLink href={p.portal_url}>Program site</ExternalLink>}
              {p.application_url ? (
                <ExternalLink href={p.application_url}>Application portal</ExternalLink>
              ) : (
                <button
                  onClick={() => setEditing(true)}
                  className={`${missingPill} ${focusRing}`}
                  title="No application portal link on file yet"
                >
                  Application portal — add it
                </button>
              )}
              {p.admissions_email ? (
                <a
                  href={`mailto:${p.admissions_email}`}
                  className={`${pill} ${focusRing}`}
                >
                  <span className="truncate">{p.admissions_email}</span>
                </a>
              ) : (
                <button
                  onClick={() => setEditing(true)}
                  className={`${missingPill} ${focusRing}`}
                  title="No admissions point of contact on file yet"
                >
                  Admissions email — add it
                </button>
              )}
              {/* "Cancel", not "Done": this opens a form you can abandon. */}
              <TextButton onClick={() => setEditing((v) => !v)}>
                {editing ? "Cancel" : "Edit"}
              </TextButton>
            </div>
          </div>

          {editing && (
            <EditHeader
              program={p}
              onSave={async (body) => {
                await api.updateProgram(pid, body);
                setEditing(false);
                reload();
              }}
            />
          )}
        </header>

        <div className="mb-3 rounded-lg border border-hairline bg-surface p-3">
          <ProgressSteps pid={pid} steps={p.steps} reload={reload} />
        </div>

        <div className="border-t-2 border-accent pt-1">
          <Tabs tabs={tabs} active={tab} onChange={setTab} />
        </div>
      </div>

      <div className="pt-6">
        {tab === "overview" && <OverviewTab {...tabProps} />}
        {tab === "faculty" && <FacultyTab {...tabProps} />}
        {tab === "docs" && <MyDocsTab {...tabProps} />}
        {tab === "notes" && <MyNotesTab {...tabProps} />}
      </div>
    </>
  );
}

/**
 * Everything the page header shows, in one form: what the program is called and
 * where its pages are. This is the only editor a program has — a researched
 * program's name and department come back from Claude, and until now there was
 * no way to correct either.
 *
 * The two URLs are separate fields because they are separate places: the
 * department runs its own site, while the application goes through the graduate
 * school's central system. A cleared field saves as null rather than "", so an
 * absent link is absent in the data too and the button stops rendering.
 * University is the one field the API requires, so an empty one blocks the save.
 */
function EditHeader({
  program,
  onSave,
}: {
  program: Detail;
  onSave: (body: {
    university: string;
    department: string | null;
    degree: string | null;
    portal_url: string | null;
    application_url: string | null;
    admissions_email: string | null;
  }) => Promise<void>;
}) {
  const [university, setUniversity] = useState(program.university);
  const [department, setDepartment] = useState(program.department ?? "");
  const [degree, setDegree] = useState(program.degree ?? "");
  const [portal, setPortal] = useState(program.portal_url ?? "");
  const [apply, setApply] = useState(program.application_url ?? "");
  const [admissionsEmail, setAdmissionsEmail] = useState(program.admissions_email ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const field = (label: string, node: React.ReactNode) => <Field label={label}>{node}</Field>;
  const cls = `${input} mt-1 w-full`;

  return (
    <form
      className="mt-3 space-y-2 rounded-lg border border-hairline bg-surface p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!university.trim()) return;
        setBusy(true);
        setError(null);
        try {
          await onSave({
            university: university.trim(),
            department: department.trim() || null,
            degree: degree.trim() || null,
            portal_url: portal.trim() || null,
            application_url: apply.trim() || null,
            admissions_email: admissionsEmail.trim() || null,
          });
        } catch (err) {
          setError(errorText(err));
        } finally {
          setBusy(false);
        }
      }}
    >
      {field(
        "University",
        <input
          className={cls}
          value={university}
          onChange={(e) => setUniversity(e.target.value)}
          required
        />,
      )}
      <div className="grid gap-2 sm:grid-cols-2">
        {field(
          "Department",
          <input
            className={cls}
            placeholder="e.g. Computer Science"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          />,
        )}
        {field(
          "Degree",
          <input
            className={cls}
            placeholder="e.g. PhD"
            value={degree}
            onChange={(e) => setDegree(e.target.value)}
          />,
        )}
      </div>
      {field(
        "Program site",
        <input
          className={cls}
          type="url"
          placeholder="https://cs.example.edu/phd"
          value={portal}
          onChange={(e) => setPortal(e.target.value)}
        />,
      )}
      {field(
        "Application portal",
        <input
          className={cls}
          type="url"
          placeholder="https://apply.example.edu/"
          value={apply}
          onChange={(e) => setApply(e.target.value)}
        />,
      )}
      {field(
        "Admissions email",
        <input
          className={cls}
          type="email"
          placeholder="admissions@example.edu"
          value={admissionsEmail}
          onChange={(e) => setAdmissionsEmail(e.target.value)}
        />,
      )}
      <Button variant="primary" type="submit" disabled={busy || !university.trim()}>
        {busy ? "Saving…" : "Save"}
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
}
