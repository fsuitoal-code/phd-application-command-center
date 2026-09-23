import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { DeadlineBadge } from "../../components/badges";
import { LinkedText, urlLabel } from "../../components/notes";
import {
  Button,
  Disclosure,
  EditToggle,
  EmptyState,
  ErrorText,
  ExternalLink,
  Panel,
  RemoveButton,
  SortableList,
  TextButton,
  input,
  textarea,
} from "../../components/ui";
import { errorText } from "../../format";
import { useAction } from "../../hooks/useAction";
import { useReorder } from "../../hooks/useReorder";
import type { MyNote } from "../../types";
import type { TabProps } from "./types";

/** "bu.edu/apply" is what people paste; the backend only takes http(s) URLs. */
function normalizeLink(value: string): string | null {
  const v = value.trim();
  if (!v) return null;
  return /^https?:\/\//i.test(v) ? v : `https://${v}`;
}

function noteLabel(n: MyNote): string {
  return n.text || n.file_name || n.link_url || "note";
}

/**
 * My Notes: the user's own scratchpad for this program. Each note is text plus,
 * optionally, a link, an attached file and a due date. Nothing here is written
 * or read by Claude.
 *
 * Laid out like every other tab — a Panel with the Overview panels' Edit
 * toggle and drag order, adding from its footer — with the tab's one
 * explanatory line as a footnote.
 */
export function MyNotesTab({ p, pid, reload }: TabProps) {
  const action = useAction();
  const reorder = useReorder(p.my_notes, (ids) => api.reorderMyNotes(pid, ids), {
    onSettled: reload,
    onError: (e) => action.setError(errorText(e)),
  });
  const [editMode, setEditMode] = useState(false);

  async function run(id: number, fn: () => Promise<unknown>) {
    if (await action.run(fn, id)) reload();
  }

  return (
    <div className="space-y-5">
      <Panel
        title="My Notes"
        action={
          reorder.order.length > 0 && (
            <EditToggle editing={editMode} onToggle={() => setEditMode((v) => !v)} />
          )
        }
        footer={
          <Disclosure label="Add note">
            {(close) => <AddMyNote pid={pid} onDone={reload} close={close} />}
          </Disclosure>
        }
      >
        {reorder.order.length === 0 ? (
          <EmptyState>No notes yet.</EmptyState>
        ) : (
          <SortableList reorder={reorder} label={noteLabel}>
            {(n, handle) => (
              <>
                {handle}
                <div className="min-w-0 flex-1 text-sm">
                  {editMode ? (
                    <EditMyNoteRow
                      pid={pid}
                      note={n}
                      busy={action.pending === n.id}
                      run={(fn) => run(n.id, fn)}
                    />
                  ) : (
                    <NoteView pid={pid} note={n} />
                  )}
                </div>
              </>
            )}
          </SortableList>
        )}
        {action.error && <ErrorText>{action.error}</ErrorText>}
      </Panel>

      <p className="px-1 text-xs text-ink-faint">
        Anything about this application you want to keep track of: links, files,
        dates, logins, reminders. Nothing here is read by Claude.
      </p>
    </div>
  );
}

function NoteView({ pid, note }: { pid: number; note: MyNote }) {
  const hasExtras = note.link_url || note.file_name || note.due_date;
  return (
    <div className="space-y-1.5">
      {note.text && (
        <p className="whitespace-pre-wrap break-words leading-relaxed">
          <LinkedText text={note.text} />
        </p>
      )}
      {hasExtras && (
        <div className="flex flex-wrap items-center gap-2">
          {note.link_url && (
            <ExternalLink href={note.link_url} title={note.link_url}>
              {urlLabel(note.link_url)}
            </ExternalLink>
          )}
          {note.file_name && (
            <ExternalLink
              href={api.myNoteFileUrl(pid, note.id)}
              title={`Open ${note.file_name}`}
              icon={<PaperclipIcon />}
            >
              {note.file_name}
            </ExternalLink>
          )}
          {note.due_date && (
            <span className="inline-flex items-center gap-1 text-xs text-ink-subtle">
              Due <DeadlineBadge date={note.due_date} />
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function PaperclipIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      className="h-3 w-3 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      aria-hidden
    >
      <path d="M10.5 4.5 5.8 9.2a1.2 1.2 0 0 0 1.7 1.7l4.9-4.9a2.5 2.5 0 0 0-3.5-3.5L4 7.4a3.7 3.7 0 0 0 5.3 5.3l4.2-4.2" />
    </svg>
  );
}

/** Hidden file input behind a text button — the native control can't be styled. */
function FilePicker({
  label,
  disabled,
  onPick,
}: {
  label: string;
  disabled?: boolean;
  onPick: (file: File) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <TextButton disabled={disabled} onClick={() => ref.current?.click()}>
        {label}
      </TextButton>
      <input
        ref={ref}
        type="file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onPick(file);
        }}
      />
    </>
  );
}

/** One optional part of a note (link, file, deadline): a label, its control, a ✕. */
function Extra({
  label,
  onRemove,
  disabled,
  children,
}: {
  label: string;
  onRemove: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 text-xs text-ink-subtle">{label}</span>
      {children}
      <RemoveButton
        label={`Remove ${label.toLowerCase()}`}
        disabled={disabled}
        onRemove={onRemove}
      />
    </div>
  );
}

function AddMyNote({
  pid,
  onDone,
  close,
}: {
  pid: number;
  onDone: () => void;
  close: () => void;
}) {
  const [text, setText] = useState("");
  const [showLink, setShowLink] = useState(false);
  const [link, setLink] = useState("");
  const [showDate, setShowDate] = useState(false);
  const [dueDate, setDueDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const { busy, error, run } = useAction();

  const linkUrl = showLink ? normalizeLink(link) : null;
  const due = showDate && dueDate ? dueDate : null;
  const hasContent = Boolean(text.trim() || linkUrl || due || file);

  return (
    <form
      className="space-y-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!hasContent) return;
        const ok = await run(() =>
          api.addMyNote(pid, { text: text.trim(), link_url: linkUrl, due_date: due, file }),
        );
        if (!ok) return;
        close();
        onDone();
      }}
    >
      <textarea
        className={`${textarea} min-h-20`}
        placeholder="Write a note…"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      {showLink && (
        <Extra
          label="Link"
          onRemove={() => {
            setShowLink(false);
            setLink("");
          }}
        >
          <input
            autoFocus
            className={`${input} min-w-0 flex-1`}
            placeholder="https://…"
            value={link}
            onChange={(e) => setLink(e.target.value)}
          />
        </Extra>
      )}
      {file && (
        <Extra label="File" onRemove={() => setFile(null)}>
          <span className="flex min-w-0 flex-1 items-center gap-1 text-sm text-ink-muted">
            <PaperclipIcon />
            <span className="truncate">{file.name}</span>
          </span>
        </Extra>
      )}
      {showDate && (
        <Extra
          label="Deadline"
          onRemove={() => {
            setShowDate(false);
            setDueDate("");
          }}
        >
          <input
            autoFocus
            type="date"
            className={input}
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </Extra>
      )}

      {(!showLink || !file || !showDate) && (
        <div className="-ml-1 flex flex-wrap items-center gap-3">
          {!showLink && <TextButton onClick={() => setShowLink(true)}>+ Link</TextButton>}
          {!file && <FilePicker label="+ File" onPick={setFile} />}
          {!showDate && <TextButton onClick={() => setShowDate(true)}>+ Deadline</TextButton>}
        </div>
      )}

      <div>
        <Button variant="primary" type="submit" disabled={busy || !hasContent}>
          {busy ? "Saving…" : "Add note"}
        </Button>
      </div>
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
}

function EditMyNoteRow({
  pid,
  note,
  busy,
  run,
}: {
  pid: number;
  note: MyNote;
  busy: boolean;
  run: (fn: () => Promise<unknown>) => void;
}) {
  const [text, setText] = useState(note.text);
  useEffect(() => setText(note.text), [note.text]);
  const [link, setLink] = useState(note.link_url ?? "");
  useEffect(() => setLink(note.link_url ?? ""), [note.link_url]);
  const [showLink, setShowLink] = useState(Boolean(note.link_url));
  const [showDate, setShowDate] = useState(Boolean(note.due_date));

  const update = (body: Parameters<typeof api.updateMyNote>[2]) =>
    run(() => api.updateMyNote(pid, note.id, body));

  return (
    <div className="space-y-2">
      <div className="flex items-start gap-2">
        <textarea
          className={`${textarea} min-w-0 flex-1`}
          rows={Math.min(10, Math.max(2, text.split("\n").length))}
          placeholder="Write a note…"
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => {
            const trimmed = text.trim();
            if (!trimmed && !note.link_url && !note.file_name && !note.due_date) {
              setText(note.text);
            } else if (trimmed !== note.text) update({ text: trimmed });
          }}
        />
        <RemoveButton
          label="Delete this note"
          disabled={busy}
          onRemove={() => run(() => api.deleteMyNote(pid, note.id))}
        />
      </div>

      {showLink && (
        <Extra
          label="Link"
          disabled={busy}
          onRemove={() => {
            setShowLink(false);
            setLink("");
            if (note.link_url) update({ link_url: null });
          }}
        >
          <input
            className={`${input} min-w-0 flex-1`}
            placeholder="https://…"
            value={link}
            disabled={busy}
            onChange={(e) => setLink(e.target.value)}
            onBlur={() => {
              const next = normalizeLink(link);
              if (next !== note.link_url) update({ link_url: next });
            }}
          />
        </Extra>
      )}
      {note.file_name && (
        <Extra
          label="File"
          disabled={busy}
          onRemove={() => run(() => api.removeMyNoteFile(pid, note.id))}
        >
          <a
            href={api.myNoteFileUrl(pid, note.id)}
            target="_blank"
            rel="noreferrer"
            className="flex min-w-0 items-center gap-1 text-sm text-ink-muted hover:text-ink"
          >
            <PaperclipIcon />
            <span className="truncate">{note.file_name}</span>
          </a>
          <FilePicker
            label="Replace"
            disabled={busy}
            onPick={(f) => run(() => api.replaceMyNoteFile(pid, note.id, f))}
          />
        </Extra>
      )}
      {showDate && (
        <Extra
          label="Deadline"
          disabled={busy}
          onRemove={() => {
            setShowDate(false);
            if (note.due_date) update({ due_date: null });
          }}
        >
          <input
            type="date"
            className={input}
            value={note.due_date ?? ""}
            disabled={busy}
            onChange={(e) => update({ due_date: e.target.value || null })}
          />
        </Extra>
      )}

      {(!showLink || !note.file_name || !showDate) && (
        <div className="-ml-1 flex flex-wrap items-center gap-3">
          {!showLink && <TextButton onClick={() => setShowLink(true)}>+ Link</TextButton>}
          {!note.file_name && (
            <FilePicker
              label="+ File"
              disabled={busy}
              onPick={(f) => run(() => api.replaceMyNoteFile(pid, note.id, f))}
            />
          )}
          {!showDate && <TextButton onClick={() => setShowDate(true)}>+ Deadline</TextButton>}
        </div>
      )}
    </div>
  );
}
