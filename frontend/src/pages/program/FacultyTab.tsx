import { useEffect, useState } from "react";
import { api } from "../../api";
import { Notes, SECTION_HEADING } from "../../components/notes";
import { SweepBar, useElapsed } from "../../components/ResearchStatus";
import {
  Button,
  Disclosure,
  EditToggle,
  EmptyState,
  ErrorText,
  ExternalLink,
  List,
  Panel,
  RemoveButton,
  SortableList,
  focusRing,
  input,
  textarea,
} from "../../components/ui";
import { errorText, formatDate } from "../../format";
import { useAction } from "../../hooks/useAction";
import { useReorder } from "../../hooks/useReorder";
import type { Faculty, FacultyNote, SuggestFacultyResult } from "../../types";
import type { TabProps } from "./types";

/**
 * The people at this program, as a short list of expandable cards.
 *
 * The shape follows from what the research pass now returns: a shortlist of at
 * most three relevant faculty rather than a department directory. Three people
 * are worth reading about; fifty-three were only ever worth scrolling past. So
 * each person gets a card that opens into the researched profile Claude wrote
 * about them, instead of a row with two buttons and no reason to press either.
 *
 * Cards carry their own sort_order (same pattern as deadlines/requirements/
 * notes/steps), so the user can drag them into whatever order they want.
 */
export function FacultyTab({ p, pid, reload }: TabProps) {
  const [error, setError] = useState<string | null>(null);
  const suggest = useAction();
  const add = useAction();
  const [suggestions, setSuggestions] = useState<SuggestFacultyResult | null>(null);
  const [suggestStartedAt, setSuggestStartedAt] = useState<number | null>(null);

  const reorder = useReorder(p.faculty, (ids) => api.reorderFaculty(pid, ids), {
    onSettled: reload,
    onError: (e) => setError(errorText(e)),
  });

  // Suggesting reads the program's own site, so it needs that site on file;
  // until then it is off, with the reason on hover.
  const suggestBlocked = !p.portal_url
    ? "Add this program's site first — Edit, at the top of the page"
    : null;

  return (
    <div className="space-y-5">
      <Panel
        title="Faculty"
        footer={
          <Disclosure label="Add faculty">
            {(close) => <AddFaculty pid={pid} onDone={reload} close={close} />}
          </Disclosure>
        }
      >
        {reorder.order.length === 0 ? (
          <EmptyState>No faculty yet.</EmptyState>
        ) : (
          <SortableList reorder={reorder} label={(f) => f.name} itemClassName="">
            {(f, handle) => (
              <FacultyCard f={f} reload={reload} dragHandle={handle} />
            )}
          </SortableList>
        )}
        {error && <ErrorText>{error}</ErrorText>}
      </Panel>

      <Panel
        title="Find more"
        action={
          <Button
            disabled={suggest.busy || suggestBlocked !== null}
            title={
              suggestBlocked ?? "Read the department site and propose people — a billed pass"
            }
            onClick={async () => {
              // A new run replaces the last one's list, so clear it up front —
              // left on screen, it reads as this run's result, or sits above
              // this run's error as if the run had half-worked.
              setSuggestions(null);
              setSuggestStartedAt(Date.now());
              await suggest.run(async () =>
                setSuggestions(await api.suggestFaculty(pid, p.portal_url ?? undefined)),
              );
              setSuggestStartedAt(null);
            }}
          >
            {suggest.busy ? "Suggesting…" : "Suggest more faculty"}
          </Button>
        }
      >
        {suggest.busy && suggestStartedAt && <SuggestingNotice startedAt={suggestStartedAt} />}
        {!suggestions && !suggest.busy && !suggest.error && (
          <EmptyState>
            {p.portal_url
              ? "Claude reads this program's official department site and proposes faculty worth contacting."
              : "Add this program's site (Edit, at the top of the page) and Claude can read it to propose faculty worth contacting."}
          </EmptyState>
        )}
        {suggestions && suggestions.faculty.length === 0 && (
          <EmptyState>
            {suggestions.already_listed.length > 0
              ? `Everyone Claude found is already on your list: ${suggestions.already_listed.join(", ")}.`
              : "Claude didn't find anyone else on the department site who fits."}
          </EmptyState>
        )}
        {suggestions && suggestions.faculty.length > 0 && (
          <List>
            {suggestions.faculty.map((s, i) => (
              <li key={i} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <span className="min-w-0">
                  <span className="font-medium">{s.name}</span>
                  {s.research_areas ? (
                    <span className="text-ink-subtle"> — {s.research_areas}</span>
                  ) : null}
                </span>
                <Button
                  disabled={add.busy}
                  onClick={async () => {
                    const ok = await add.run(
                      () =>
                        api.addFaculty(pid, {
                          name: s.name,
                          research_areas: s.research_areas,
                          homepage_url: s.homepage_url ?? undefined,
                        }),
                      i,
                    );
                    if (!ok) return;
                    // Now on the list, so reported as such: adding everyone
                    // must not leave "Claude didn't find anyone" behind.
                    setSuggestions(
                      (cur) =>
                        cur && {
                          faculty: cur.faculty.filter((x) => x !== s),
                          already_listed: [...cur.already_listed, s.name],
                        },
                    );
                    reload();
                  }}
                >
                  {add.pending === i ? "Adding…" : "Add"}
                </Button>
              </li>
            ))}
          </List>
        )}
        {suggestions &&
          suggestions.faculty.length > 0 &&
          suggestions.already_listed.length > 0 && (
            <p className="pt-2 text-xs text-ink-subtle">
              Also found, already on your list: {suggestions.already_listed.join(", ")}.
            </p>
          )}
        {(suggest.error || add.error) && <ErrorText>{suggest.error ?? add.error}</ErrorText>}
      </Panel>
    </div>
  );
}

/**
 * One faculty member: a header that stays useful collapsed, and a body that
 * holds everything researched about them.
 */
function FacultyCard({
  f,
  reload,
  dragHandle,
}: {
  f: Faculty;
  reload: () => void;
  dragHandle: React.ReactNode;
}) {
  // Always collapsed on arrival — a long researched list should stay
  // scannable when you switch to this tab, not unfold into a wall of
  // dossiers. `run()` still opens a card the moment its own research
  // finishes, so the result of pressing "Research" is never hidden.
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  /**
   * The failure of THIS person's action, kept on this card.
   *
   * It used to be one error for the whole tab, rendered under the last panel
   * on the page. With a list this long that put the explanation a thousand
   * pixels below the button that caused it: you pressed Research, waited four
   * minutes, the spinner cleared, and nothing appeared to have happened. A
   * failed pass has already cost real money, so its reason belongs where you
   * are looking.
   */
  const [error, setError] = useState<string | null>(null);
  // Only "research" needs a clock — it's the only pass long enough for an
  // elapsed counter to mean anything against "delete", which resolves at
  // request-round-trip speed.
  const [researchStartedAt, setResearchStartedAt] = useState<number | null>(null);

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    if (label === "research") setResearchStartedAt(Date.now());
    try {
      await fn();
      setOpen(true);
      reload();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
      setResearchStartedAt(null);
    }
  }

  const researched = Boolean(f.dossier);

  return (
    <div className="py-3 text-sm">
      <div
        className={`flex items-start justify-between gap-3 ${
          // Pinned only while there's a dossier underneath worth scrolling
          // through — a collapsed card has nothing to lose the name behind.
          // Sits below the page's own sticky header + program header (the
          // combined var(--header-h) + var(--program-header-h)), so a long
          // profile can scroll under it without swallowing whose it is.
          open ? "sticky z-[3] -mx-4 border-b border-hairline-soft bg-surface px-4 py-2" : ""
        }`}
        style={
          open
            ? { top: "calc(var(--header-h, 64px) + var(--program-header-h, 0px))" }
            : undefined
        }
      >
        <div className="flex min-w-0 flex-1 items-start gap-1">
          {dragHandle}
          <button
            onClick={() => setOpen(!open)}
            className={`flex min-w-0 flex-1 items-start gap-2 rounded text-left ${focusRing}`}
            aria-expanded={open}
          >
            <span className="mt-0.5 shrink-0 text-ink-faint">{open ? "▾" : "▸"}</span>
            <span className="min-w-0">
              {/* The name is the card's title: display serif, full ink, a size
                  up — set against the small sans research line beneath it, so
                  the two never read as one run of text. */}
              <span className="flex flex-wrap items-baseline gap-2">
                <span className="font-display text-base font-semibold leading-snug text-ink">
                  {f.name}
                </span>
                {f.contacted && <span className="text-xs text-ink-faint">contacted</span>}
                {researched && (
                  <span className="text-xs text-ink-faint">researched</span>
                )}
              </span>
              {f.research_areas && (
                <span className="mt-1 block text-xs text-ink-subtle">
                  {f.research_areas}
                </span>
              )}
            </span>
          </button>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {f.homepage_url && (
            <ExternalLink href={f.homepage_url} title={`${f.name}'s faculty or lab page`}>
              Website
            </ExternalLink>
          )}
          <Button
            variant={researched ? "quiet" : "primary"}
            disabled={busy !== null}
            title={
              researched
                ? "Research this person again — a new billed pass"
                : "Read their pages and write a cited profile — a billed pass, a few minutes"
            }
            onClick={() => run("research", () => api.researchFaculty(f.id))}
          >
            {busy === "research"
              ? "Researching…"
              : researched
                ? "Re-research"
                : "Research"}
          </Button>
          <RemoveButton
            label={`Remove ${f.name}`}
            confirm={`Remove ${f.name} from this program?`}
            disabled={busy !== null}
            onRemove={() => run("delete", () => api.deleteFaculty(f.id))}
          />
        </div>
      </div>

      {/* Outside the `open` block on purpose: a pass can fail while the card
          is collapsed, and that is exactly the case where silence looks like
          nothing happened. The message says what it cost, so it is not
          dismissed on a timer either — and it gets a rule, unlike a routine
          form error, because it is the one failure that cost money. */}
      {error && (
        <p className="mt-2 border-l-2 border-danger pl-3 text-xs leading-relaxed text-danger">
          {error}
        </p>
      )}

      {open && (
        <div className="mt-3 border-l-2 border-hairline-soft pl-4">
          {/* No title of its own: the dossier opens on "Bottom line", which is
              already the heading a profile needs. */}
          <div>
            {busy === "research" && researchStartedAt && (
              // Unlike a program pass, this one writes to the database when it
              // finishes whether or not the browser is still listening — so
              // leaving costs you the notification, not the dossier.
              <ResearchingNotice name={f.name} startedAt={researchStartedAt} />
            )}
            {!researched && busy !== "research" && (
              <EmptyState>
                Not researched yet. Research reads their faculty page, lab site and
                group page and writes a profile where every claim quotes its source.
              </EmptyState>
            )}
            {f.dossier && (
              <>
                {/* Claude's own read, which is the one thing here that is not a
                    quote from a page. Labelled, so it is not mistaken for one. */}
                <Notes text={f.dossier} />
                {f.dossier_researched_at && (
                  <p className="pt-1 text-xs text-ink-faint">
                    Researched {formatDate(f.dossier_researched_at)}
                    {f.dossier_model ? ` · ${f.dossier_model}` : ""} · unverified
                  </p>
                )}
              </>
            )}
          </div>

          <FacultyNotes facultyId={f.id} notes={f.notes} reload={reload} />
        </div>
      )}
    </div>
  );
}

/**
 * The in-progress notice for a Claude pass on this tab, styled to match the
 * program-research strip in the header (same pulsing dot, sweep bar and
 * elapsed counter) so "Claude is working" reads the same way everywhere in
 * the app. Scoped to its panel rather than the header — neither the dossier
 * nor the suggest pass has a cross-page store, only local `busy` state.
 */
function WorkingNotice({
  label,
  startedAt,
  children,
}: {
  label: React.ReactNode;
  startedAt: number;
  children: React.ReactNode;
}) {
  const elapsed = useElapsed(startedAt);
  return (
    <div className="relative overflow-hidden rounded border border-hairline-soft bg-surface-muted px-3 py-2">
      <div className="flex items-center gap-2">
        <span
          className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-accent motion-reduce:animate-none"
          aria-hidden
        />
        <span className="min-w-0 flex-1 text-xs text-ink-muted">{label}</span>
        <span className="shrink-0 tabular-nums text-xs text-ink-faint">{elapsed}</span>
      </div>
      <p className="mt-1.5 text-xs text-ink-subtle">{children}</p>
      <SweepBar />
    </div>
  );
}

function ResearchingNotice({ name, startedAt }: { name: string; startedAt: number }) {
  return (
    <WorkingNotice
      startedAt={startedAt}
      label={
        <>
          Reading <span className="text-ink">{name}</span>'s pages…
        </>
      }
    >
      You can leave this page; the profile is saved when the pass finishes, and
      reopening this person will show it. A refresh probably won't stop it either
      — but closing the app will, and the pass is billed either way.
    </WorkingNotice>
  );
}

/**
 * Unlike a dossier, suggestions are never written to the database — they only
 * come back in the response — so here leaving the page does lose the result.
 */
function SuggestingNotice({ startedAt }: { startedAt: number }) {
  return (
    <WorkingNotice startedAt={startedAt} label="Claude is reading the department site…">
      This usually takes a minute or two. Stay on this tab: suggestions aren't
      saved, so leaving the page discards them, and the pass is billed
      either way.
    </WorkingNotice>
  );
}

/**
 * The user's own notes about this person -- unlike the researched profile
 * above, nothing Claude writes ends up here, so there's no citation or
 * verify badge, just text the user typed and can drag into order. Same Edit
 * toggle as the Overview panels.
 */
function FacultyNotes({
  facultyId,
  notes,
  reload,
}: {
  facultyId: number;
  notes: FacultyNote[];
  reload: () => void;
}) {
  const action = useAction();
  const reorder = useReorder(notes, (ids) => api.reorderFacultyNotes(facultyId, ids), {
    onSettled: reload,
    onError: (e) => action.setError(errorText(e)),
  });
  const [editMode, setEditMode] = useState(false);

  async function change(id: number, fn: () => Promise<unknown>) {
    if (await action.run(fn, id)) reload();
  }

  return (
    <Section
      title="Notes"
      action={
        reorder.order.length > 0 && (
          <EditToggle editing={editMode} onToggle={() => setEditMode((v) => !v)} />
        )
      }
    >
      {reorder.order.length === 0 ? (
        <EmptyState>No notes yet.</EmptyState>
      ) : (
        <SortableList reorder={reorder} label={(n) => n.text}>
          {(n, handle) => (
            <>
              {handle}
              <div className="min-w-0 flex-1 text-sm">
                {editMode ? (
                  <EditFacultyNoteRow
                    note={n}
                    busy={action.pending === n.id}
                    onSave={(text) =>
                      change(n.id, () => api.updateFacultyNote(facultyId, n.id, { text }))
                    }
                    onDelete={() => change(n.id, () => api.deleteFacultyNote(facultyId, n.id))}
                  />
                ) : (
                  <p className="break-words">{n.text}</p>
                )}
              </div>
            </>
          )}
        </SortableList>
      )}
      <Disclosure label="Add note">
        {(close) => <AddFacultyNote facultyId={facultyId} onDone={reload} close={close} />}
      </Disclosure>
      {action.error && <ErrorText>{action.error}</ErrorText>}
    </Section>
  );
}

function EditFacultyNoteRow({
  note,
  busy,
  onSave,
  onDelete,
}: {
  note: FacultyNote;
  busy: boolean;
  onSave: (text: string) => void;
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
          if (trimmed && trimmed !== note.text) onSave(trimmed);
          else setText(note.text);
        }}
      />
      <RemoveButton label="Delete this note" disabled={busy} onRemove={onDelete} />
    </div>
  );
}

function AddFacultyNote({
  facultyId,
  onDone,
  close,
}: {
  facultyId: number;
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
        if (!(await run(() => api.addFacultyNote(facultyId, { text: trimmed })))) return;
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

/**
 * The Notes block under a faculty card's profile, with its own action on the
 * right. Styled as one more dossier section — same rule above, same heading
 * as "Bottom line", "Research" and the rest — since it continues the same
 * page about this person.
 */
function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-6 border-t border-hairline pt-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className={SECTION_HEADING}>{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}

function AddFaculty({
  pid,
  onDone,
  close,
}: {
  pid: number;
  onDone: () => void;
  close: () => void;
}) {
  const [name, setName] = useState("");
  const [areas, setAreas] = useState("");
  const { busy, error, run } = useAction();
  return (
    <form
      className="flex flex-wrap gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!name.trim()) return;
        const ok = await run(() =>
          api.addFaculty(pid, { name: name.trim(), research_areas: areas || null }),
        );
        if (!ok) return;
        setName("");
        setAreas("");
        close();
        onDone();
      }}
    >
      <input
        className={input}
        placeholder="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className={`${input} min-w-0 flex-1`}
        placeholder="Research areas"
        value={areas}
        onChange={(e) => setAreas(e.target.value)}
      />
      <Button variant="primary" type="submit" disabled={busy || !name.trim()}>
        Add
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
}
