import { useEffect, useState } from "react";
import { Link } from "react-router";
import { researchStore, type ResearchRun } from "../research";
import { focusRing } from "./ui";

/**
 * The strip under the header bar that says a research pass is still going.
 *
 * A pass runs for minutes with nothing else on screen to show for it, so the
 * elapsed counter is the point: it is the difference between "still working"
 * and "did this die when I changed pages?".
 */
export function ResearchStatus({ run }: { run: ResearchRun }) {
  return (
    <div className="relative border-t border-hairline-soft bg-surface-muted">
      {run.state === "running" && <SweepBar />}
      {/* Wraps rather than truncating the warning away on a narrow window. */}
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-2 gap-y-0.5 px-4 py-1.5 text-xs">
        {run.state === "running" ? (
          <Running run={run} />
        ) : run.state === "done" ? (
          <>
            <span className="text-ink-muted">
              Added <span className="text-ink">{run.program.university}</span>
            </span>
            <Link
              to={`/programs/${run.program.id}`}
              className={`rounded text-ink-subtle underline decoration-hairline-strong underline-offset-2 transition-colors hover:text-ink ${focusRing}`}
            >
              Open
            </Link>
            <Dismiss />
          </>
        ) : (
          <>
            <span className="min-w-0 flex-1 truncate text-danger" title={run.error}>
              {run.error}
            </span>
            <Dismiss />
          </>
        )}
      </div>
    </div>
  );
}

/**
 * The indeterminate bar along the bottom edge of the strip. There is no
 * progress to report — the pass writes nothing until it finishes — so this
 * says "alive", not "halfway".
 *
 * Exported so other in-progress notices (the faculty dossier card) can reuse
 * the same "alive, not halfway" visual language instead of inventing their own.
 */
export function SweepBar() {
  return (
    <div
      className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-hairline-soft"
      aria-hidden
    >
      <div className="h-full w-1/4 rounded-full bg-accent animate-research-sweep motion-reduce:w-full motion-reduce:animate-none motion-reduce:opacity-60" />
    </div>
  );
}

function Running({ run }: { run: Extract<ResearchRun, { state: "running" }> }) {
  const elapsed = useElapsed(run.startedAt);
  useBlockUnload();
  return (
    <>
      <span
        className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-accent motion-reduce:animate-none"
        aria-hidden
      />
      <span className="min-w-[8rem] flex-1 truncate text-ink-muted">
        Researching <span className="text-ink">{run.query}</span>…
      </span>
      {/* The pass survives moving around the app; it does not survive the
          document being torn down. Say which is which — "keep this tab open"
          read as "don't go anywhere", which is the opposite of the point. */}
      <span className="shrink-0 text-ink-subtle">
        Switching pages is fine — just don't refresh
      </span>
      <span className="shrink-0 tabular-nums text-ink-faint">{elapsed}</span>
    </>
  );
}

/**
 * Ask the browser to confirm before a reload or a close while a pass is
 * running. Mounted only while `running`, so the listener's life is the pass's.
 *
 * A refresh cannot be undone from here: it takes the fetch down with the
 * document, and the pass has already been billed. The backend request may well
 * run on to completion server-side, but the app has no way to find out, so the
 * honest thing is to stop the refresh happening.
 */
function useBlockUnload() {
  useEffect(() => {
    const confirmLeave = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Older browsers need this set; the string itself is never shown.
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", confirmLeave);
    return () => window.removeEventListener("beforeunload", confirmLeave);
  }, []);
}

function Dismiss() {
  return (
    <button
      onClick={() => researchStore.dismiss()}
      title="Dismiss"
      aria-label="Dismiss"
      className={`ml-auto shrink-0 rounded px-1 text-ink-ghost transition-colors hover:text-ink ${focusRing}`}
    >
      ✕
    </button>
  );
}

/**
 * Ticking "2m 14s" since `startedAt`.
 *
 * Exported for the same reason as `SweepBar` — the faculty dossier notice
 * ticks its own elapsed time and shouldn't duplicate the interval logic.
 */
export function useElapsed(startedAt: number): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}
