import { useEffect, useState, useSyncExternalStore } from "react";
import { Link } from "react-router";
import { api } from "../api";
import { researchStore } from "../research";
import { AddProgramForm } from "../components/AddProgramForm";
import { DeadlineColumn } from "../components/badges";
import {
  Button,
  DragHandle,
  EmptyState,
  ErrorText,
  focusRing,
  Loading,
  ProgressBar,
  RemoveButton,
} from "../components/ui";
import { errorText, programName } from "../format";
import { useReorder } from "../hooks/useReorder";
import { useTitle } from "../hooks/useTitle";
import type { ProgramSummary } from "../types";

// Stable empty list for useReorder while loading — a fresh `[]` each render
// would resync its order forever.
const NONE: ProgramSummary[] = [];

export default function ProgramList() {
  useTitle("Programs");
  const [programs, setPrograms] = useState<ProgramSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  async function reload() {
    try {
      setPrograms(await api.listPrograms());
    } catch (e) {
      setError(errorText(e));
    }
  }

  useEffect(() => {
    reload();
  }, []);

  // A pass started here can finish while the user is on another page, and the
  // mount-time fetch above has long since returned. Without this the new
  // program stays invisible until a full reload.
  const research = useSyncExternalStore(researchStore.subscribe, researchStore.get);
  useEffect(() => {
    if (research?.state === "done") reload();
  }, [research]);

  const reorder = useReorder(programs ?? NONE, api.reorderPrograms, {
    onSettled: reload,
    onError: (e) => setError(errorText(e)),
  });

  async function onDelete(p: ProgramSummary) {
    setError(null);
    try {
      await api.deleteProgram(p.id);
    } catch (e) {
      setError(errorText(e));
    }
    reload();
  }

  return (
    <>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Programs</h1>
          <Summary programs={programs} />
        </div>
        <Button variant={adding ? "quiet" : "primary"} onClick={() => setAdding(!adding)}>
          {adding ? "Cancel" : "+ Add program"}
        </Button>
      </header>

      {adding && (
        <div className="mb-6">
          <AddProgramForm
            onAdded={() => {
              setAdding(false);
              reload();
            }}
          />
        </div>
      )}

      {error && <ErrorText>{error}</ErrorText>}

      {programs === null && !error && <Loading />}

      {programs && programs.length === 0 && !adding && (
        <EmptyState>
          No programs yet. Add one — let Claude research it, or enter it manually.
        </EmptyState>
      )}

      {programs && programs.length > 0 && (
        <ul className="divide-y divide-hairline-soft border-y border-hairline">
          {reorder.order.map((p, i) => (
            <li
              key={p.id}
              {...reorder.dragProps(i)}
              // The page sits on the canvas colour, so a hovered row lifts off
              // it as a surface card — the only cue that the whole row is one
              // click target. z-[1] keeps the shadow over its neighbours but
              // under the sticky header (z-10). `isolate` contains the drag
              // handle's own z-10 inside this row, so it can't leak above the
              // sticky header on scroll either.
              className={`group isolate relative flex flex-col gap-2 rounded-lg px-2 py-3 transition hover:z-[1] hover:-translate-y-px hover:bg-surface hover:shadow-sm ${
                p.urgency === "overdue" ? "border-l-2 border-l-danger-solid" : ""
              } ${reorder.dragClass(i)}`}
            >
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                <div className="flex min-w-0 items-center gap-2">
                  <DragHandle
                    label={p.university}
                    onMove={(delta) => reorder.move(i, i + delta)}
                  />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <Link
                        to={`/programs/${p.id}`}
                        draggable={false}
                        className={`truncate rounded text-sm font-medium after:absolute after:inset-0 ${focusRing}`}
                      >
                        {p.university}
                      </Link>
                      {p.is_stale && (
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full bg-warning-solid"
                          title="Idle with a deadline approaching — needs attention"
                        />
                      )}
                    </div>
                    <div className="truncate text-xs text-ink-subtle">
                      {programName(p.degree, p.department)}
                    </div>
                  </div>
                </div>

                <div className="-ml-1.5 flex shrink-0 items-center gap-3 pl-7 sm:ml-0 sm:pl-0">
                  <DeadlineColumn date={p.application_deadline} />
                  {/* relative lifts the button over the Link's after:inset-0
                      row overlay, which would otherwise swallow the click. */}
                  <RemoveButton
                    label={`Delete ${p.university}`}
                    confirm={`Delete ${p.university}? This removes all its data.`}
                    onRemove={() => onDelete(p)}
                    className="relative z-[1]"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pl-7">
                <div className="max-w-40 flex-1">
                  <ProgressBar
                    pct={p.steps_total ? (p.steps_completed / p.steps_total) * 100 : 0}
                  />
                </div>
                <span className="text-xs tabular-nums text-ink-faint">
                  {p.steps_completed} of {p.steps_total} done
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/**
 * Only what needs acting on. The program count said nothing the list itself
 * doesn't, so the line stays empty until something is actually urgent.
 */
function Summary({ programs }: { programs: ProgramSummary[] | null }) {
  if (!programs) return null;

  const overdue = programs.filter((p) => p.urgency === "overdue").length;
  const dueSoon = programs.filter((p) => p.urgency === "due_soon").length;
  const stale = programs.filter((p) => p.is_stale).length;

  const parts = [
    overdue > 0 ? `${overdue} overdue` : null,
    dueSoon > 0 ? `${dueSoon} due within 14 days` : null,
    stale > 0 ? `${stale} need attention` : null,
  ].filter(Boolean);

  if (parts.length === 0) return null;

  return <p className="mt-0.5 text-sm text-ink-subtle">{parts.join(" · ")}</p>;
}
