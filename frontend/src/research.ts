/**
 * The one in-flight Claude research pass, held outside React's tree.
 *
 * A pass takes minutes and bills the user's own subscription, so it has to stay visible wherever the user goes. It used to live
 * entirely inside `AddProgramForm` — the busy flag and the completion callback
 * both — which meant clicking through to the Dossier unmounted the component,
 * threw away every trace that a pass was running, and left the finished program
 * invisible until a full page reload.
 *
 * So the run lives here, in a module, and the header and the program list
 * subscribe to it via `useSyncExternalStore`. No context, no dependency: there
 * is exactly one of these at a time and the app has no state library.
 *
 * This survives navigation, not a reload — Ctrl+R kills the document and the
 * fetch with it, and by then the pass has already been billed. Surviving that
 * needs a server-side job, which is a bigger decision than this file.
 */

import { api } from "./api";
import type { ProgramDetail } from "./types";

export type ResearchRun =
  | { state: "running"; query: string; startedAt: number }
  | { state: "done"; query: string; program: ProgramDetail }
  | { state: "failed"; query: string; error: string };

let current: ResearchRun | null = null;
const listeners = new Set<() => void>();

function set(run: ResearchRun | null) {
  current = run;
  for (const listener of listeners) listener();
}

export const researchStore = {
  /** For useSyncExternalStore. Returns an unsubscribe. */
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },

  /** The snapshot: a stable reference that changes only on a transition. */
  get(): ResearchRun | null {
    return current;
  },

  /** Clear a finished or failed run from the header. */
  dismiss() {
    if (current?.state !== "running") set(null);
  },

  /**
   * Run a pass, recording it so every page can see it.
   *
   * Still resolves/rejects to the caller, so the add form can react inline
   * while it happens to be mounted.
   */
  async start(query: string, officialUrl: string): Promise<ProgramDetail> {
    // One at a time. A form's disabled button cannot enforce this: navigating
    // away and back remounts it re-enabled, so the guard belongs where the
    // knowledge does.
    if (current?.state === "running") {
      throw new Error("A research pass is already running.");
    }
    set({ state: "running", query, startedAt: Date.now() });
    try {
      const program = await api.researchProgram(query, officialUrl);
      set({ state: "done", query, program });
      return program;
    } catch (err) {
      // The message alone: the backend's detail already reads as a sentence
      // ("Research failed: …"), and
      // String(err) would prefix it with a bare "Error:".
      set({
        state: "failed",
        query,
        error: err instanceof Error ? err.message : String(err),
      });
      throw err;
    }
  },
};
