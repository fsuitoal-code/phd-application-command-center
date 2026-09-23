import { useRef, useState } from "react";
import { api } from "../api";
import { errorText } from "../format";
import { useAction } from "../hooks/useAction";
import { useReorder } from "../hooks/useReorder";
import {
  Button,
  Disclosure,
  EditToggle,
  ErrorText,
  ProgressBar,
  RemoveButton,
  focusRing,
  input,
} from "./ui";
import type { ProgramStep } from "../types";

/**
 * The application checklist. Every tick is an explicit user action — nothing
 * here infers completion from the presence of other data, so "gathered but
 * still incomplete" stays expressible.
 *
 * Eight-plus labels can't be a segmented bar (unreadable on desktop, hopeless
 * at 375px), so the steps are wrapping chips over a single thin progress bar.
 * Order is user-controlled too — drag a chip to reorder — same pattern as
 * the program list's row reordering.
 *
 * The Edit toggle on the right, not a button per chip, switches what a click
 * on a chip does: toggle complete normally, rename while editing — same
 * right-side placement as the page header's own Edit above. The delete ✕
 * only appears in edit mode too, so it can't be clicked by accident while
 * just ticking steps off.
 */
export function ProgressSteps({
  pid,
  steps,
  reload,
}: {
  pid: number;
  steps: ProgramStep[];
  reload: () => void;
}) {
  const action = useAction();
  const { error, setError } = action;

  // Same reorder as every other list; chips wrap, so the drop target shows as
  // a ring rather than a line above.
  const reorder = useReorder(steps, (ids) => api.reorderSteps(pid, ids), {
    onSettled: reload,
    onError: (e) => setError(errorText(e)),
  });
  const { order } = reorder;

  // Renaming a chip in place, behind a section-level Edit toggle rather than
  // a per-chip button: click doubles as "toggle complete" normally and
  // "rename" while editing, so there's one control for the whole checklist
  // instead of one per step. Any step — built-in or custom — can be renamed
  // or removed now: BUILTIN_STEPS only seeds what a new program starts with.
  const [editMode, setEditMode] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");
  // Escape and a successful Enter-save both trigger the input's blur (via
  // unmount or explicit blur) right after already handling it — this skips
  // that redundant second save/cancel.
  const skipNextBlur = useRef(false);

  const done = order.filter((s) => s.completed).length;
  const pct = order.length ? (done / order.length) * 100 : 0;

  async function run(id: number, fn: () => Promise<unknown>) {
    if (await action.run(fn, id)) reload();
  }

  function startEdit(s: ProgramStep) {
    // Reset here, not just after consuming it on blur: the previous edit's
    // Enter-triggered unmount doesn't reliably fire a blur event to consume
    // the flag itself, so a stale `true` would otherwise swallow this edit's
    // legitimate blur-to-save.
    skipNextBlur.current = false;
    setEditingId(s.id);
    setEditValue(s.label);
  }

  function cancelEdit() {
    skipNextBlur.current = true;
    setEditingId(null);
  }

  async function saveEdit(id: number) {
    const value = editValue.trim();
    setEditingId(null);
    const current = order.find((s) => s.id === id);
    if (!value || !current || current.label === value) return;
    await run(id, () => api.renameStep(pid, id, value));
  }

  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h2 className="text-sm font-medium">Progress</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs tabular-nums text-ink-subtle">
            {done} of {order.length} done
          </span>
          <EditToggle editing={editMode} onToggle={() => setEditMode((v) => !v)} />
        </div>
      </div>

      <div className="mb-2">
        <ProgressBar pct={pct} />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {order.map((s, i) =>
          editingId === s.id ? (
            <input
              key={s.id}
              autoFocus
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  skipNextBlur.current = true;
                  saveEdit(s.id);
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  cancelEdit();
                }
              }}
              onBlur={() => {
                if (skipNextBlur.current) {
                  skipNextBlur.current = false;
                  return;
                }
                saveEdit(s.id);
              }}
              className="w-32 rounded-full border border-accent bg-surface px-2.5 py-1 text-xs text-ink outline-none"
            />
          ) : (
            <span
              key={s.id}
              {...reorder.dragProps(i)}
              className={`group relative inline-flex items-center rounded-full border text-xs transition-colors ${
                s.completed
                  ? "border-success-edge bg-success-surface text-success-strong hover:border-success-edge-hover"
                  : "border-hairline text-ink-soft hover:border-hairline-strong hover:bg-canvas"
              } ${reorder.dragClass(i, "ring")}`}
            >
              <button
                disabled={action.pending === s.id}
                onClick={() =>
                  editMode
                    ? startEdit(s)
                    : run(s.id, () => api.setStep(pid, s.id, !s.completed))
                }
                title={
                  editMode
                    ? "Click to rename"
                    : s.completed && s.completed_at
                      ? `Completed ${new Date(s.completed_at + "Z").toLocaleDateString()} — click to undo`
                      : "Mark complete"
                }
                className={`rounded-full py-1 pl-2.5 pr-6 disabled:opacity-40 ${focusRing}`}
              >
                {s.label}
              </button>
              {editMode && (
                <RemoveButton
                  label={`Remove ${s.label}`}
                  onRemove={() => run(s.id, () => api.deleteStep(pid, s.id))}
                  className="absolute right-1 top-1/2 -translate-y-1/2 px-0.5! text-[10px]!"
                />
              )}
            </span>
          ),
        )}

        <Disclosure label="Add step">
          {(close) => <AddStep pid={pid} onDone={reload} close={close} />}
        </Disclosure>
      </div>

      {error && <ErrorText>{error}</ErrorText>}
    </div>
  );
}

function AddStep({
  pid,
  onDone,
  close,
}: {
  pid: number;
  onDone: () => void;
  close: () => void;
}) {
  const [label, setLabel] = useState("");
  const { busy, error, run } = useAction();
  return (
    <form
      className="flex flex-wrap gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!label.trim()) return;
        if (await run(() => api.addStep(pid, label.trim()))) {
          setLabel("");
          close();
          onDone();
        }
      }}
    >
      <input
        className={`${input} min-w-0 flex-1`}
        placeholder="e.g. Writing sample"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
      />
      <Button variant="primary" type="submit" disabled={busy || !label.trim()}>
        Add
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
}
