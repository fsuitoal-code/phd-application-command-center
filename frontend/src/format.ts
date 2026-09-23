// Display formatting shared by every page, so the same value never reads two
// different ways in two places.

/** A thrown value as a sentence: backend details already read as one, so
 * drop the "Error:" prefix `String(e)` would add. */
export function errorText(e: unknown): string {
  return (e instanceof Error ? e.message : String(e)).replace(/^Error:\s*/, "");
}

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * One date format for the whole app — "Jan 08, 2027" in the viewer's locale.
 *
 * Takes either a date-only value ("2027-01-08", read as local midnight so it
 * can't slip a day in a timezone west of UTC) or a backend timestamp. The
 * backend stores naive UTC (`utcnow`), so a timestamp without a zone is UTC.
 * Two-digit days keep a column of dates the same width.
 */
export function formatDate(value: string): string {
  const d = DATE_ONLY.test(value)
    ? new Date(value + "T00:00:00")
    : new Date(HAS_ZONE.test(value) ? value : value + "Z");
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

/**
 * The stored degree and department are each written out in full — "PhD in
 * Business Administration, Operations & Technology Management concentration"
 * next to "Operations & Technology Management (Questrom School of Business)".
 * A short label only needs the credential and the field: "PhD Operations &
 * Technology Management". The program's own page still shows both in full.
 */
export function programName(degree: string | null, department: string | null): string {
  // Everything after "in" or a comma is the long form of the field, which the
  // department says more briefly.
  const credential = (degree ?? "").split(/\s+in\s+|,/)[0].trim();
  // Drop the school the department sits inside: "… (Questrom School of Business)".
  const field = (department ?? "").replace(/\s*\([^)]*\)\s*$/, "").trim();

  if (!credential) return field || "—";
  if (!field) return credential;
  // Don't repeat the field when one already contains the other.
  const [c, f] = [credential.toLowerCase(), field.toLowerCase()];
  if (f.startsWith(c)) return field;
  if (c.endsWith(f)) return credential;
  return `${credential} ${field}`;
}
