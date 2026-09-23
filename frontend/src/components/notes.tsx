/**
 * Renderer for cited Claude output: a program's notes, and a faculty dossier.
 *
 * Both contracts (backend/app/claude/research.py "NOTES FORMAT", and
 * app/claude/faculty_dossier.py) produce the same markdown — bullets that cite
 * the page each fact came from as `[label](url)`, with the quoted sentence on
 * a `> ` line beneath. A dossier adds `## ` headings, because it is a profile
 * in named sections rather than one list; notes never contain them, so one
 * renderer serves both and neither needs to know about the other.
 *
 * This renders exactly that much markdown and nothing else. The input is model
 * output, so the syntax honoured here stays deliberately small and every href
 * is scheme-checked before it becomes an anchor. Notes written before the
 * contract asked for bullets are plain prose and still render as paragraphs,
 * one per line, as they did before.
 */

/** Leading marker of a bullet line: "- ", "* " or "• ". */
const BULLET = /^[-*•]\s+/;

/** Leading marker of a dossier section heading: "## Funding". */
const HEADING = /^#{1,6}\s+/;

/** Leading marker of a quote line: the source sentence under a bullet. */
const QUOTE = /^>\s*/;

/** `[label](url)` first, then a bare http(s) URL. */
const LINK_SOURCE =
  "\\[([^\\]\\n]+)\\]\\(([^()\\s]+)\\)|(https?://[^\\s<>()\\[\\]]+)";

/** Sentence punctuation that trailed a bare URL rather than belonging to it. */
const TRAILING_PUNCTUATION = /[.,;:!?]+$/;

/**
 * A dossier section heading ("Bottom line", "Research", …). Exported so the
 * faculty card's own "Notes" heading, which follows the dossier, reads as
 * one more section of the same profile rather than a different level.
 */
export const SECTION_HEADING =
  "text-xs font-bold uppercase tracking-widest text-ink";

const LINK_CLASS =
  "text-ink underline decoration-hairline-strong underline-offset-2 transition-colors hover:decoration-ink";

/** Only http(s) becomes a link; anything else (javascript:, data:) stays text. */
function safeHref(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.href
      : null;
  } catch {
    return null;
  }
}

/**
 * An uncited bare URL is shown as host + last path segment — the whole string
 * is unreadable inline, but the host alone does not say which page it is.
 */
export function urlLabel(url: string): string {
  try {
    const { hostname, pathname } = new URL(url);
    const host = hostname.replace(/^www\./, "");
    const segments = pathname.split("/").filter(Boolean);
    const last = segments[segments.length - 1];
    return last ? `${host}/…/${last}` : host;
  } catch {
    return url;
  }
}

function renderInline(text: string, key: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  // Fresh regex per call: a shared /g literal carries lastIndex between calls.
  const pattern = new RegExp(LINK_SOURCE, "g");
  let cursor = 0;
  let n = 0;

  for (const match of text.matchAll(pattern)) {
    const [raw, label, markdownUrl, bareUrl] = match;
    const start = match.index ?? 0;
    if (start > cursor) out.push(text.slice(cursor, start));
    cursor = start + raw.length;

    // A bare URL swallows the sentence's full stop; hand it back to the text.
    let url = markdownUrl ?? bareUrl ?? "";
    let tail = "";
    if (bareUrl) {
      const trimmed = bareUrl.replace(TRAILING_PUNCTUATION, "");
      tail = bareUrl.slice(trimmed.length);
      url = trimmed;
    }

    const href = safeHref(url);
    if (href) {
      out.push(
        <a
          key={`${key}-${n++}`}
          href={href}
          target="_blank"
          rel="noreferrer"
          title={href}
          className={LINK_CLASS}
        >
          {label ?? urlLabel(href)}
        </a>,
      );
      if (tail) out.push(tail);
    } else {
      out.push(raw);
    }
  }

  if (cursor < text.length) out.push(text.slice(cursor));
  return out;
}

/**
 * User-typed text as-is — line breaks kept by the caller's `whitespace-pre-wrap`
 * — with `[label](url)` and bare URLs made clickable.
 */
export function LinkedText({ text }: { text: string }) {
  return <>{renderInline(text, "t")}</>;
}

/** A bullet, plus the source sentence backing it when the note carries one. */
interface Item {
  text: string;
  quote?: string;
}

type Block =
  | { kind: "list"; items: Item[] }
  | { kind: "para"; text: string }
  | { kind: "heading"; text: string };

/**
 * Group the lines into headings, bullet lists and paragraphs. Consecutive
 * bullets are one list; consecutive prose lines are one paragraph (this is
 * model output, so a break mid-sentence is wrapping, not an intended line
 * break). A "> " line attaches to the bullet above it as that fact's quote.
 * A blank line, or a heading, closes whichever block is open.
 */
function toBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  let openParagraph = false;

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) {
      openParagraph = false;
      continue;
    }
    const last = blocks[blocks.length - 1];
    if (HEADING.test(line)) {
      openParagraph = false;
      const text = line.replace(HEADING, "").trim();
      if (text) blocks.push({ kind: "heading", text });
    } else if (BULLET.test(line)) {
      openParagraph = false;
      const item = line.replace(BULLET, "");
      if (last?.kind === "list") last.items.push({ text: item });
      else blocks.push({ kind: "list", items: [{ text: item }] });
    } else if (QUOTE.test(line) && last?.kind === "list") {
      openParagraph = false;
      const quote = line.replace(QUOTE, "");
      const item = last.items[last.items.length - 1];
      // A second quote line for one bullet is a wrapped sentence, not a
      // second source; join it rather than dropping it.
      item.quote = item.quote ? `${item.quote} ${quote}` : quote;
    } else if (openParagraph && last?.kind === "para") {
      last.text += " " + line;
    } else {
      blocks.push({ kind: "para", text: line.replace(QUOTE, "") });
      openParagraph = true;
    }
  }
  return blocks;
}

export function Notes({ text }: { text: string }) {
  const blocks = toBlocks(text);
  if (blocks.length === 0) return null;
  return (
    <div className="space-y-2.5 py-2 text-sm leading-relaxed text-ink-muted">
      {blocks.map((block, i) =>
        block.kind === "heading" ? (
          // A rule above each heading (after the first) is what keeps a
          // multi-section dossier from reading as one long undifferentiated
          // list — the divider marks where one theme (Research, Funding, …)
          // ends and the next begins. Full-strength ink and a wider gap above
          // than below make the heading outrank the body text it introduces
          // (text-ink-muted) rather than blend into it, and set it apart from
          // the card's header above it. The first section loses the rule
          // and the extra top space so the dossier does not open with a gap.
          <h3
            key={i}
            className={`mt-6 border-t border-hairline pt-3 first:mt-0 first:border-t-0 first:pt-0 ${SECTION_HEADING}`}
          >
            {block.text}
          </h3>
        ) : block.kind === "list" ? (
          <ul
            key={i}
            className="list-disc divide-y divide-hairline-soft pl-4 marker:text-ink-faint"
          >
            {block.items.map((item, j) => (
              <li key={j} className="break-words py-1.5 first:pt-0 last:pb-0">
                {renderInline(item.text, `${i}-${j}`)}
                {item.quote && (
                  // The source's own words, so the claim above can be checked
                  // without following the link. Quiet, because the summary is
                  // what the reader is scanning.
                  <q className="mt-1 block border-l-2 border-hairline pl-2 text-xs italic text-ink-subtle before:content-none after:content-none">
                    {item.quote}
                  </q>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p key={i} className="break-words">
            {renderInline(block.text, `${i}`)}
          </p>
        ),
      )}
    </div>
  );
}
