import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import {
  Button,
  Disclosure,
  EmptyState,
  ErrorText,
  ExternalLink,
  List,
  Loading,
  Panel,
  RemoveButton,
  TextButton,
  input,
} from "../../components/ui";
import { errorText, formatDate } from "../../format";
import { useAction } from "../../hooks/useAction";
import type { DocFile, DocType } from "../../types";
import type { TabProps } from "./types";

type Run = (fn: () => Promise<unknown>, key?: unknown) => Promise<boolean>;

/**
 * My Docs: a small file registry, per program. CV and Statement of Purpose
 * are seeded for every new program; the user can add, rename, or delete any
 * type from here on — built-in or custom, same rule the application
 * checklist already follows. Each program's documents are independent — a
 * CV or SOP tailored to one program never shows up on another's tab.
 *
 * Pure storage. Nothing here is read by Claude — the two features that used
 * to read a doc's content (per-program CV review, faculty fit) are both gone,
 * so a type is just a title and a list of files the user can open.
 *
 * Laid out like every other tab: a stack of Panels, each adding to itself
 * from its footer, with the tab's one explanatory line as a footnote.
 */
export function MyDocsTab({ pid }: TabProps) {
  const [types, setTypes] = useState<DocType[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const action = useAction();

  async function reload() {
    try {
      setTypes(await api.getDocs(pid));
    } catch (e) {
      setLoadError(errorText(e));
    }
  }
  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  /** Run a change, then reload — every control on the tab goes through this. */
  const run: Run = async (fn, key) => {
    const ok = await action.run(fn, key);
    if (ok) await reload();
    return ok;
  };

  if (loadError) return <ErrorText>{loadError}</ErrorText>;
  if (types === null) return <Loading />;

  return (
    <div className="space-y-5">
      {types.map((t) => (
        <DocTypePanel key={t.id} docType={t} pid={pid} busy={action.busy} run={run} />
      ))}

      {types.length === 0 && <EmptyState>No document types yet.</EmptyState>}

      <div className="px-1">
        <Disclosure label="Add document type">
          {(close) => (
            <AddDocType
              busy={action.busy}
              onAdd={async (title) => {
                if (await run(() => api.addDocType(pid, title))) close();
              }}
            />
          )}
        </Disclosure>
      </div>

      {action.error && <ErrorText>{action.error}</ErrorText>}

      <p className="px-1 text-xs text-ink-faint">
        This program's own copies — stored on this computer so they're in one place.
        Nothing here is read by Claude.
      </p>
    </div>
  );
}

function DocTypePanel({
  docType,
  pid,
  busy,
  run,
}: {
  docType: DocType;
  pid: number;
  busy: boolean;
  run: Run;
}) {
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState(docType.title);
  const fileRef = useRef<HTMLInputElement>(null);
  // Escape unmounts the field, and an unmount can still deliver a blur —
  // this stops that blur saving the text Escape just threw away.
  const cancelled = useRef(false);

  useEffect(() => setTitle(docType.title), [docType.title]);

  // Renamed the way a checklist step is: the title becomes a field, Enter or
  // leaving it saves, Escape puts the old name back.
  async function save() {
    if (cancelled.current) return;
    const next = title.trim();
    setRenaming(false);
    if (!next || next === docType.title) {
      setTitle(docType.title);
      return;
    }
    await run(() => api.renameDocType(docType.id, next));
  }

  const n = docType.files.length;

  return (
    <Panel
      title={
        renaming ? (
          <input
            autoFocus
            aria-label="Document type name"
            className={`${input} py-0.5`}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={save}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                e.currentTarget.blur();
              } else if (e.key === "Escape") {
                cancelled.current = true;
                setTitle(docType.title);
                setRenaming(false);
              }
            }}
          />
        ) : (
          docType.title
        )
      }
      action={
        !renaming && (
          <>
            <TextButton
              disabled={busy}
              onClick={() => {
                cancelled.current = false;
                setRenaming(true);
              }}
            >
              Rename
            </TextButton>
            <RemoveButton
              label={`Delete ${docType.title}`}
              confirm={
                n > 0
                  ? `Delete ${docType.title} and its ${n} file${n === 1 ? "" : "s"}?`
                  : `Delete ${docType.title}?`
              }
              disabled={busy}
              onRemove={() => run(() => api.deleteDocType(docType.id))}
            />
          </>
        )
      }
      footer={
        <>
          {/* The browser's own file control can't be themed, so it stays
              hidden and this "+ Upload file" opens it — the same footer
              "+ Add" every other panel has. */}
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              run(() => api.uploadDocFile(pid, docType.id, file)).finally(() => {
                if (fileRef.current) fileRef.current.value = "";
              });
            }}
          />
          <TextButton
            disabled={busy}
            onClick={() => fileRef.current?.click()}
            className="-ml-1 mt-1"
          >
            + Upload file
          </TextButton>
        </>
      }
    >
      {n === 0 ? (
        <EmptyState>No files yet.</EmptyState>
      ) : (
        <List>
          {docType.files.map((f) => (
            <FileRow key={f.id} file={f} busy={busy} run={run} />
          ))}
        </List>
      )}
    </Panel>
  );
}

function FileRow({ file, busy, run }: { file: DocFile; busy: boolean; run: Run }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2.5 text-sm">
      <div className="min-w-0">
        <span className="block truncate font-medium" title={file.filename}>
          {file.filename}
        </span>
        <span className="text-xs text-ink-faint">Added {formatDate(file.created_at)}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <ExternalLink href={api.docFileUrl(file.id)}>Open</ExternalLink>
        <RemoveButton
          label={`Delete ${file.filename}`}
          confirm={`Delete ${file.filename}?`}
          disabled={busy}
          onRemove={() => run(() => api.deleteDocFile(file.id))}
        />
      </div>
    </li>
  );
}

function AddDocType({
  busy,
  onAdd,
}: {
  busy: boolean;
  onAdd: (title: string) => void;
}) {
  const [title, setTitle] = useState("");
  return (
    <form
      className="flex flex-wrap gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!title.trim()) return;
        onAdd(title.trim());
      }}
    >
      <input
        autoFocus
        className={`${input} min-w-0 flex-1 sm:max-w-xs`}
        placeholder="e.g. Writing sample"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <Button variant="primary" type="submit" disabled={busy || !title.trim()}>
        Add
      </Button>
    </form>
  );
}
