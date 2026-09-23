import { useRef, useState } from "react";
import type { Reorder } from "../hooks/useReorder";

// ── Focus ────────────────────────────────────────────────────────────────
// One keyboard-focus treatment for every control: an accent ring, shown only
// for keyboard focus so a mouse click doesn't leave a ring behind.
export const focusRing =
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50";

// ── Field tokens ─────────────────────────────────────────────────────────
// One definition for every text control in the app: a hairline border that
// firms up on focus.
export const input =
  "rounded-md border border-hairline bg-surface px-2.5 py-1.5 text-sm placeholder:text-ink-faint focus:border-hairline-strong focus:outline-none";
export const select = input;
export const textarea = `${input} w-full`;

/** A labelled form field — the label above, the control below it. */
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-ink-subtle">{label}</span>
      {children}
    </label>
  );
}

// ── Type tokens ──────────────────────────────────────────────────────────
/** Small-caps label: table column heads, a card's section names, a tag. */
export const eyebrow = "text-xs font-medium uppercase tracking-wide text-ink-subtle";

// ── Button ───────────────────────────────────────────────────────────────
type Variant = "primary" | "quiet" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-on-accent hover:bg-accent-hover disabled:hover:bg-accent",
  quiet:
    "border border-hairline text-ink-muted hover:border-hairline-strong hover:bg-canvas",
  ghost: "text-ink-subtle hover:text-ink",
};

export function Button({
  variant = "quiet",
  className = "",
  ...rest
}: { variant?: Variant } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      className={`rounded-md px-2.5 py-1 text-xs transition-colors disabled:opacity-40 ${focusRing} ${VARIANTS[variant]} ${className}`}
    />
  );
}

/**
 * The quietest control: faint text that darkens on hover. For secondary
 * actions that sit beside content rather than compete with it — Edit/Done,
 * Rename, Cancel, "+ Add …".
 */
export function TextButton({
  className = "",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...rest}
      className={`rounded px-1 text-xs text-ink-faint transition-colors hover:text-ink disabled:opacity-40 ${focusRing} ${className}`}
    />
  );
}

/**
 * The Edit/Done switch in a section's heading. Edit mode is where rows can be
 * changed or deleted; leaving it is "Done", because nothing is abandoned —
 * every field saves as you leave it. (A form you can abandon says "Cancel".)
 */
export function EditToggle({
  editing,
  onToggle,
}: {
  editing: boolean;
  onToggle: () => void;
}) {
  return <TextButton onClick={onToggle}>{editing ? "Done" : "Edit"}</TextButton>;
}

/**
 * The ✕ that removes something. `label` is what it removes, for the tooltip
 * and screen readers. Pass `confirm` when the ✕ is always visible or the loss
 * is large — a delete that sits behind an Edit toggle has already been asked
 * for once and doesn't need it.
 *
 * Hover turns it danger-red: the one use of that colour outside the deadline
 * contract, because a destructive control should look it before it's pressed.
 */
export function RemoveButton({
  label,
  confirm,
  onRemove,
  disabled,
  className = "",
}: {
  label: string;
  confirm?: string;
  onRemove: () => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={() => {
        if (confirm && !window.confirm(confirm)) return;
        onRemove();
      }}
      className={`rounded px-1 text-xs text-ink-ghost transition-colors hover:text-danger disabled:opacity-40 ${focusRing} ${className}`}
    >
      ✕
    </button>
  );
}

// ── Links ────────────────────────────────────────────────────────────────
/** The outlined shape every "go somewhere else" link uses. */
export const pill =
  "inline-flex max-w-full items-center gap-1 rounded-md border border-hairline px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-hairline-strong hover:bg-canvas";

/**
 * A link that leaves the app — a program's site, a faculty page, an uploaded
 * file. Always a pill with a ↗ and always a new tab, so it reads as "opens
 * elsewhere" wherever it appears. (A citation inside text is different: it
 * stays an underlined inline link, see notes.tsx.)
 */
export function ExternalLink({
  href,
  title,
  icon,
  children,
}: {
  href: string;
  title?: string;
  /** A small leading glyph, e.g. a paperclip for an attached file. */
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      title={title}
      className={`${pill} ${focusRing}`}
    >
      {icon}
      {/* A long label (a pasted URL, a file name) truncates; the arrow stays. */}
      <span className="truncate">{children}</span>
      <span aria-hidden>↗</span>
    </a>
  );
}

// ── Progress bar ─────────────────────────────────────────────────────────
/** A thin fill bar for a 0-100 percentage. Purely visual — no label, no
 * click handler; callers own any surrounding text. */
export function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-surface-muted">
      <div
        className="h-full rounded-full bg-success-solid transition-all duration-300"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Layout helpers ───────────────────────────────────────────────────────
/**
 * A titled panel — the unit of separation between sections. A white card on
 * the neutral page, a heading bar, a divided body, and an optional footer for
 * the section's own "+ Add" action.
 */
export function Panel({
  title,
  action,
  footer,
  children,
}: {
  title: React.ReactNode;
  /** Controls aligned to the right of the heading bar. */
  action?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    // No `overflow-hidden` here: it would clip nothing else in this box (the
    // body and footer carry no background of their own, so the section's own
    // rounded bg-surface already shows through them correctly), but it does
    // silently break `position: sticky` for anything inside — any non-visible
    // overflow value on an ancestor, even one that never actually overflows,
    // stops a descendant from sticking to the viewport (a faculty card's name
    // row relies on this). The header's own bg-surface-muted is the one child
    // whose background is otherwise square, so it gets the top corners itself.
    <section className="rounded-lg border border-hairline bg-surface">
      <div className="flex items-center justify-between gap-3 rounded-t-lg border-b border-hairline bg-surface-muted px-4 py-2">
        <h2 className="flex min-w-0 items-baseline gap-2 text-sm font-medium text-ink">
          {title}
        </h2>
        {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
      </div>
      <div className="px-4 py-1">{children}</div>
      {footer && (
        <div className="border-t border-hairline-soft px-4 py-2">{footer}</div>
      )}
    </section>
  );
}

/** A hairline-divided list. Replaces one-bordered-card-per-item. */
export function List({ children }: { children: React.ReactNode }) {
  return <ul className="divide-y divide-hairline-soft">{children}</ul>;
}

/**
 * A List whose rows the user can drag (or arrow-key) into their own order.
 * `children` renders one row and is handed that row's drag handle to place —
 * most rows put it first, but a faculty card tucks it into its own header.
 */
export function SortableList<T extends { id: number }>({
  reorder,
  label,
  itemClassName = "flex items-start gap-2 py-2.5",
  children,
}: {
  reorder: Reorder<T>;
  /** Names the row for the handle's tooltip and screen readers. */
  label: (item: T) => string;
  itemClassName?: string;
  children: (item: T, handle: React.ReactNode) => React.ReactNode;
}) {
  return (
    <List>
      {reorder.order.map((item, i) => (
        <li
          key={item.id}
          {...reorder.dragProps(i)}
          className={`isolate transition ${itemClassName} ${reorder.dragClass(i)}`}
        >
          {children(
            item,
            <DragHandle
              label={label(item)}
              onMove={(delta) => reorder.move(i, i + delta)}
            />,
          )}
        </li>
      ))}
    </List>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <p className="py-3 text-sm text-ink-faint">{children}</p>;
}

export function Loading() {
  return <EmptyState>Loading…</EmptyState>;
}

/** A failure, shown where it happened. Takes a full row inside a wrapping
 * form, so it sits under the controls rather than beside them. */
export function ErrorText({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 basis-full break-words text-xs text-danger">{children}</p>;
}

// ── Disclosure ───────────────────────────────────────────────────────────
/**
 * A "+ Add" trigger that reveals an inline form. The render prop receives a
 * `close` callback so a form can collapse itself after a successful submit.
 */
export function Disclosure({
  label = "Add",
  children,
}: {
  label?: string;
  children: (close: () => void) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <TextButton onClick={() => setOpen(true)} className="-ml-1 mt-1">
        + {label}
      </TextButton>
    );
  }
  return (
    <div className="mt-2">
      {children(() => setOpen(false))}
      <TextButton onClick={() => setOpen(false)} className="-ml-1 mt-1">
        Cancel
      </TextButton>
    </div>
  );
}

/**
 * Six-dot grip for a draggable row. Arrow keys move the row too, so
 * reordering doesn't require a mouse — HTML5 drag-and-drop covers neither
 * keyboards nor touch on its own. Shared by every manually-orderable list
 * (programs, steps, deadlines).
 */
export function DragHandle({
  label,
  onMove,
}: {
  label: string;
  onMove: (delta: number) => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  return (
    <button
      ref={ref}
      type="button"
      onKeyDown={(e) => {
        if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
        e.preventDefault();
        onMove(e.key === "ArrowUp" ? -1 : 1);
        // Keep focus on the handle so the row can be moved repeatedly.
        requestAnimationFrame(() => ref.current?.focus());
      }}
      title={`Drag to reorder ${label}, or use the arrow keys`}
      aria-label={`Reorder ${label}`}
      className={`relative z-10 shrink-0 cursor-grab rounded p-1 text-ink-ghost transition-colors hover:text-ink active:cursor-grabbing ${focusRing}`}
    >
      <svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true">
        {[2, 7, 12].map((y) =>
          [2, 8].map((x) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="1.3" fill="currentColor" />
          )),
        )}
      </svg>
    </button>
  );
}

// ── Tabs ─────────────────────────────────────────────────────────────────
export interface Tab<T extends string> {
  id: T;
  label: string;
}

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: Tab<T>[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div role="tablist" className="-mb-px flex gap-1 overflow-x-auto border-b border-hairline">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={`shrink-0 rounded-t border-b-2 px-3 py-2 text-sm transition-colors ${focusRing} ${
            active === t.id
              ? "border-accent font-medium text-ink"
              : "border-transparent text-ink-subtle hover:text-ink"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
