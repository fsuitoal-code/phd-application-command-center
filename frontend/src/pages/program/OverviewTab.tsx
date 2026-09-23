import { useEffect, useState } from "react";
import { api } from "../../api";
import {
  ConfirmFact,
  DeadlineBadge,
  humanize,
  humanizeRequirementKind,
} from "../../components/badges";
import {
  Button,
  Disclosure,
  EditToggle,
  EmptyState,
  ErrorText,
  Panel,
  RemoveButton,
  SortableList,
  input,
  textarea,
} from "../../components/ui";
import { errorText } from "../../format";
import { useAction } from "../../hooks/useAction";
import { useReorder } from "../../hooks/useReorder";
import { type Deadline, type ProgramNote, type Requirement } from "../../types";
import type { TabProps } from "./types";

export function OverviewTab({ p, pid, reload }: TabProps) {
  return (
    <div className="space-y-5">
      <DeadlinesPanel pid={pid} deadlines={p.deadlines} reload={reload} />

      <RequirementsPanel pid={pid} requirements={p.requirements} reload={reload} />

      <NotesPanel pid={pid} notes={p.notes} reload={reload} />

      {/* Provenance for the researched facts above (Rule 8). Absent on a
          hand-added program, and on anything researched before it was
          recorded — the config only says what a pass would use today. */}
      {p.research_model && (
        <p className="px-1 text-xs text-ink-faint">
          Facts researched with {p.research_model}.
        </p>
      )}
    </div>
  );
}

/**
 * What every Overview panel shares: a user-ordered list (drag is always on,
 * it isn't destructive), an Edit toggle that gates changing or deleting a row
 * (a stray click shouldn't change a date or delete one), and one error line
 * for whatever a row's controls last failed at.
 */
function useEditableList<T extends { id: number }>(
  items: T[],
  saveOrder: (ids: number[]) => Promise<unknown>,
  reload: () => void,
) {
  const action = useAction();
  const reorder = useReorder(items, saveOrder, {
    onSettled: reload,
    onError: (e) => action.setError(errorText(e)),
  });
  const [editMode, setEditMode] = useState(false);

  /** Run a row's change, then reload; `key` marks which row is busy. */
  async function change(key: unknown, fn: () => Promise<unknown>) {
    if (await action.run(fn, key)) reload();
  }

  const toggle =
    reorder.order.length > 0 ? (
      <EditToggle editing={editMode} onToggle={() => setEditMode((v) => !v)} />
    ) : null;

  return { reorder, editMode, toggle, change, pending: action.pending, error: action.error };
}

/**
 * Deadlines carry their own sort_order, so the user can drag them into
 * whatever order they want — the date/urgency badge still shows per row
 * regardless, and its colour walks from neutral to amber to red as the date
 * approaches.
 */
function DeadlinesPanel({
  pid,
  deadlines,
  reload,
}: {
  pid: number;
  deadlines: Deadline[];
  reload: () => void;
}) {
  const list = useEditableList(deadlines, (ids) => api.reorderDeadlines(pid, ids), reload);

  return (
    <Panel
      title="Deadlines"
      action={list.toggle}
      footer={
        <Disclosure label="Add deadline">
          {(close) => <AddDeadline pid={pid} onDone={reload} close={close} />}
        </Disclosure>
      }
    >
      {list.reorder.order.length === 0 ? (
        <EmptyState>No deadlines yet.</EmptyState>
      ) : (
        <SortableList reorder={list.reorder} label={(d) => humanize(d.type)}>
          {(d, handle) => (
            <>
              {handle}
              <div className="min-w-0 flex-1 text-sm">
                {list.editMode ? (
                  <EditDeadlineRow
                    deadline={d}
                    busy={list.pending === d.id}
                    onSave={(patch) =>
                      list.change(d.id, () => api.updateDeadline(pid, d.id, patch))
                    }
                    onDelete={() => list.change(d.id, () => api.deleteDeadline(pid, d.id))}
                  />
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 break-words">
                      <span className="font-medium text-ink">{humanize(d.type)}</span>
                      {d.notes && (
                        <span className="ml-1.5 text-xs text-ink-subtle">{d.notes}</span>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <DeadlineBadge date={d.date} />
                      {/* Only a Claude-researched date needs this: a blank
                          placeholder has nothing to verify, and anything typed
                          in by hand is already confirmed. */}
                      {d.source !== "confirmed_by_program" && d.date && (
                        <ConfirmFact
                          source={d.source}
                          needsVerification={d.needs_human_verification}
                          disabled={list.pending === d.id}
                          onConfirm={() =>
                            list.change(d.id, () => api.confirmDeadline(pid, d.id))
                          }
                        />
                      )}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </SortableList>
      )}
      {list.error && <ErrorText>{list.error}</ErrorText>}
    </Panel>
  );
}

function EditDeadlineRow({
  deadline,
  busy,
  onSave,
  onDelete,
}: {
  deadline: Deadline;
  busy: boolean;
  onSave: (patch: { type?: string; date?: string | null; notes?: string | null }) => void;
  onDelete: () => void;
}) {
  // Type and notes are both free text, buffered locally and saved on blur
  // (same as the checklist's rename field) — a save per keystroke would spam
  // the API and fight the reload.
  const [type, setType] = useState(deadline.type);
  useEffect(() => setType(deadline.type), [deadline.type]);
  const [notes, setNotes] = useState(deadline.notes ?? "");
  useEffect(() => setNotes(deadline.notes ?? ""), [deadline.notes]);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        className={input}
        placeholder="Type"
        value={type}
        disabled={busy}
        onChange={(e) => setType(e.target.value)}
        onBlur={() => {
          const trimmed = type.trim();
          if (trimmed && trimmed !== deadline.type) onSave({ type: trimmed });
          else setType(deadline.type);
        }}
      />
      <input
        type="date"
        className={input}
        value={deadline.date ?? ""}
        disabled={busy}
        onChange={(e) => onSave({ date: e.target.value || null })}
      />
      <input
        className={`${input} min-w-0 flex-1`}
        placeholder="Notes"
        value={notes}
        disabled={busy}
        onChange={(e) => setNotes(e.target.value)}
        onBlur={() => {
          if (notes !== (deadline.notes ?? "")) onSave({ notes: notes || null });
        }}
      />
      <RemoveButton
        label={`Delete ${humanize(deadline.type)}`}
        disabled={busy}
        onRemove={onDelete}
      />
    </div>
  );
}

function AddDeadline({
  pid,
  onDone,
  close,
}: {
  pid: number;
  onDone: () => void;
  close: () => void;
}) {
  const [type, setType] = useState("");
  const [date, setDate] = useState("");
  const [notes, setNotes] = useState("");
  const { busy, error, run } = useAction();
  return (
    <form
      className="flex flex-wrap gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        const trimmed = type.trim();
        if (!date || !trimmed) return;
        const ok = await run(() =>
          api.addDeadline(pid, { type: trimmed, date, notes: notes.trim() || null }),
        );
        if (!ok) return;
        setType("");
        setDate("");
        setNotes("");
        close();
        onDone();
      }}
    >
      <input
        className={input}
        placeholder="Type"
        value={type}
        onChange={(e) => setType(e.target.value)}
      />
      <input
        type="date"
        className={input}
        value={date}
        onChange={(e) => setDate(e.target.value)}
      />
      <input
        className={`${input} min-w-0 flex-1`}
        placeholder="Notes"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      <Button variant="primary" type="submit" disabled={busy || !date || !type.trim()}>
        Add
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
}

/**
 * Requirements behave like Deadlines: every new program is seeded with the
 * six built-in kinds (GRE, TOEFL, Application Fee, Fee Waiver, Recommendation
 * Letters, Essay Type), and from there the list is fully the user's own —
 * edited in place, deleted, dragged into any order, or added to for anything
 * else (a writing sample, a portfolio).
 */
function RequirementsPanel({
  pid,
  requirements,
  reload,
}: {
  pid: number;
  requirements: Requirement[];
  reload: () => void;
}) {
  const list = useEditableList(
    requirements,
    (ids) => api.reorderRequirements(pid, ids),
    reload,
  );

  return (
    <Panel
      title="Requirements"
      action={list.toggle}
      footer={
        <Disclosure label="Add requirement">
          {(close) => <AddRequirement pid={pid} onDone={reload} close={close} />}
        </Disclosure>
      }
    >
      {list.reorder.order.length === 0 ? (
        <EmptyState>No requirements yet.</EmptyState>
      ) : (
        <SortableList reorder={list.reorder} label={(r) => humanizeRequirementKind(r.kind)}>
          {(r, handle) => (
            <>
              {handle}
              <div className="min-w-0 flex-1 text-sm">
                {list.editMode ? (
                  <EditRequirementRow
                    requirement={r}
                    busy={list.pending === r.id}
                    onSave={(patch) =>
                      list.change(r.id, () => api.updateRequirement(pid, r.id, patch))
                    }
                    onDelete={() =>
                      list.change(r.id, () => api.deleteRequirement(pid, r.id))
                    }
                  />
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 break-words">
                      <span className="font-medium text-ink">
                        {humanizeRequirementKind(r.kind)}
                      </span>
                      <span className="ml-1.5 text-xs text-ink-subtle">
                        {r.value || <span className="text-ink-faint">—</span>}
                      </span>
                    </div>
                    {/* Only a Claude-researched fact needs this: a blank
                        placeholder has nothing to verify, and anything typed
                        in by hand is already confirmed (see RequirementCreate). */}
                    {r.source !== "confirmed_by_program" && r.value && (
                      <ConfirmFact
                        source={r.source}
                        needsVerification={r.needs_human_verification}
                        disabled={list.pending === r.id}
                        onConfirm={() =>
                          list.change(r.id, () => api.confirmRequirement(pid, r.id))
                        }
                      />
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </SortableList>
      )}
      {list.error && <ErrorText>{list.error}</ErrorText>}
    </Panel>
  );
}

function EditRequirementRow({
  requirement,
  busy,
  onSave,
  onDelete,
}: {
  requirement: Requirement;
  busy: boolean;
  onSave: (patch: { kind?: string; value?: string | null }) => void;
  onDelete: () => void;
}) {
  // Kind and value are both free text, buffered locally and saved on blur —
  // same as EditDeadlineRow, so a save per keystroke doesn't spam the API.
  const [kind, setKind] = useState(requirement.kind);
  useEffect(() => setKind(requirement.kind), [requirement.kind]);
  const [value, setValue] = useState(requirement.value ?? "");
  useEffect(() => setValue(requirement.value ?? ""), [requirement.value]);

  const isRecLetters = requirement.kind === "rec_letters";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        className={input}
        placeholder="Requirement"
        value={kind}
        disabled={busy}
        onChange={(e) => setKind(e.target.value)}
        onBlur={() => {
          const trimmed = kind.trim();
          if (trimmed && trimmed !== requirement.kind) onSave({ kind: trimmed });
          else setKind(requirement.kind);
        }}
      />
      <input
        className={`${input} min-w-0 flex-1`}
        type={isRecLetters ? "number" : "text"}
        min={isRecLetters ? 0 : undefined}
        placeholder="Value"
        value={value}
        disabled={busy}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => {
          if (value !== (requirement.value ?? "")) onSave({ value: value || null });
        }}
      />
      <RemoveButton
        label={`Delete ${humanizeRequirementKind(requirement.kind)}`}
        disabled={busy}
        onRemove={onDelete}
      />
    </div>
  );
}

function AddRequirement({
  pid,
  onDone,
  close,
}: {
  pid: number;
  onDone: () => void;
  close: () => void;
}) {
  const [kind, setKind] = useState("");
  const [value, setValue] = useState("");
  const { busy, error, run } = useAction();
  return (
    <form
      className="flex flex-wrap gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        const trimmed = kind.trim();
        if (!trimmed) return;
        const ok = await run(() =>
          api.addRequirement(pid, { kind: trimmed, value: value || null }),
        );
        if (!ok) return;
        setKind("");
        setValue("");
        close();
        onDone();
      }}
    >
      <input
        className={input}
        placeholder="Requirement"
        value={kind}
        onChange={(e) => setKind(e.target.value)}
      />
      <input
        className={`${input} min-w-0 flex-1`}
        placeholder="Value"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <Button variant="primary" type="submit" disabled={busy || !kind.trim()}>
        Add
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
}

/**
 * Notes behave like Requirements/Deadlines: each is its own row (not a
 * markdown blob), edited in place, deleted, dragged into any order, or
 * added to by hand. The citation (quote + source link) is read-only —
 * it's the record of what the source said, not something to correct.
 */
function NotesPanel({
  pid,
  notes,
  reload,
}: {
  pid: number;
  notes: ProgramNote[];
  reload: () => void;
}) {
  const list = useEditableList(notes, (ids) => api.reorderNotes(pid, ids), reload);

  return (
    <Panel
      title="Researched facts"
      action={list.toggle}
      footer={
        <Disclosure label="Add fact">
          {(close) => <AddNote pid={pid} onDone={reload} close={close} />}
        </Disclosure>
      }
    >
      {list.reorder.order.length === 0 ? (
        <EmptyState>No facts yet.</EmptyState>
      ) : (
        <SortableList reorder={list.reorder} label={(n) => n.text}>
          {(n, handle) => (
            <>
              {handle}
              <div className="min-w-0 flex-1 text-sm">
                {list.editMode ? (
                  <EditNoteRow
                    note={n}
                    busy={list.pending === n.id}
                    onSave={(patch) =>
                      list.change(n.id, () => api.updateNote(pid, n.id, patch))
                    }
                    onDelete={() => list.change(n.id, () => api.deleteNote(pid, n.id))}
                  />
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="break-words">{n.text}</p>
                      {n.quote && (
                        <q className="mt-1 block border-l-2 border-hairline pl-2 text-xs italic text-ink-subtle before:content-none after:content-none">
                          {n.quote}
                        </q>
                      )}
                      {n.source_url && (
                        // A citation, so an inline underlined link like the
                        // dossier's — not the pill an outbound page link gets.
                        <a
                          href={n.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 inline-block break-all text-xs text-ink-faint underline decoration-hairline-strong underline-offset-2 transition-colors hover:text-ink hover:decoration-ink"
                        >
                          {n.source_label || n.source_url}
                        </a>
                      )}
                    </div>
                    {/* Only a Claude-researched fact needs this: a hand-added
                        or uncited note has nothing to verify. */}
                    {n.source !== "confirmed_by_program" && n.quote && (
                      <ConfirmFact
                        source={n.source}
                        needsVerification={n.needs_human_verification}
                        disabled={list.pending === n.id}
                        onConfirm={() => list.change(n.id, () => api.confirmNote(pid, n.id))}
                      />
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </SortableList>
      )}
      {list.error && <ErrorText>{list.error}</ErrorText>}
    </Panel>
  );
}

function EditNoteRow({
  note,
  busy,
  onSave,
  onDelete,
}: {
  note: ProgramNote;
  busy: boolean;
  onSave: (patch: { text: string }) => void;
  onDelete: () => void;
}) {
  const [text, setText] = useState(note.text);
  useEffect(() => setText(note.text), [note.text]);

  return (
    <div className="flex flex-wrap items-start gap-2">
      <textarea
        className={`${textarea} min-w-0 flex-1`}
        rows={2}
        value={text}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          const trimmed = text.trim();
          if (trimmed && trimmed !== note.text) onSave({ text: trimmed });
          else setText(note.text);
        }}
      />
      <RemoveButton label="Delete this note" disabled={busy} onRemove={onDelete} />
    </div>
  );
}

function AddNote({
  pid,
  onDone,
  close,
}: {
  pid: number;
  onDone: () => void;
  close: () => void;
}) {
  const [text, setText] = useState("");
  const { busy, error, run } = useAction();
  return (
    <form
      className="flex flex-wrap gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        const trimmed = text.trim();
        if (!trimmed) return;
        if (!(await run(() => api.addNote(pid, { text: trimmed })))) return;
        setText("");
        close();
        onDone();
      }}
    >
      <textarea
        className={`${textarea} min-w-0 flex-1`}
        rows={2}
        placeholder="Note"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <Button variant="primary" type="submit" disabled={busy || !text.trim()}>
        Add
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
}
