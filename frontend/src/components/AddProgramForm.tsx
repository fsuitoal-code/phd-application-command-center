import { useState, useSyncExternalStore } from "react";
import { api } from "../api";
import { researchStore } from "../research";
import { errorText } from "../format";
import { Button, ErrorText, Field, Tabs, input } from "./ui";
import type { ProgramDetail } from "../types";

type Mode = "manual" | "research";

export function AddProgramForm({ onAdded }: { onAdded: (p: ProgramDetail) => void }) {
  const [mode, setMode] = useState<Mode>("research");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The research pass is owned by the store, not by this form — it outlives
  // both. Reading it here keeps the button honest after a remount, when local
  // `busy` has been reset but the pass is still going.
  const research = useSyncExternalStore(researchStore.subscribe, researchStore.get);
  const researching = research?.state === "running";

  // manual fields
  const [university, setUniversity] = useState("");
  const [department, setDepartment] = useState("");
  const [portalUrl, setPortalUrl] = useState("");
  const [applicationUrl, setApplicationUrl] = useState("");
  const [degree, setDegree] = useState("");
  const [admissionsEmail, setAdmissionsEmail] = useState("");

  // research fields
  const [researchUniversity, setResearchUniversity] = useState("");
  const [researchDepartment, setResearchDepartment] = useState("");
  const [officialUrl, setOfficialUrl] = useState("");

  async function submitManual(e: React.FormEvent) {
    e.preventDefault();
    if (!university.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createProgram({
        university: university.trim(),
        department: department.trim() || null,
        degree: degree.trim() || null,
        portal_url: portalUrl.trim() || null,
        application_url: applicationUrl.trim() || null,
        admissions_email: admissionsEmail.trim() || null,
      });
      setUniversity("");
      setDepartment("");
      setPortalUrl("");
      setApplicationUrl("");
      setDegree("");
      setAdmissionsEmail("");
      onAdded(created);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitResearch(e: React.FormEvent) {
    e.preventDefault();
    if (!researchUniversity.trim() || !officialUrl.trim()) return;
    setError(null);
    try {
      const query = [researchUniversity.trim(), researchDepartment.trim()]
        .filter(Boolean)
        .join(", ");
      const created = await researchStore.start(query, officialUrl.trim());
      setResearchUniversity("");
      setResearchDepartment("");
      setOfficialUrl("");
      onAdded(created);
    } catch (err) {
      // The header shows this too; keep it inline for whoever stayed put.
      setError(errorText(err));
    }
  }

  // Same fields, labels and order as the program page's Edit form, so a
  // program is described the same way whether it's being added or corrected.
  const cls = `${input} mt-1 w-full`;

  return (
    <div className="rounded-lg border border-hairline bg-surface p-4">
      <div className="mb-4">
        <Tabs
          tabs={[
            { id: "research", label: "Let Claude research it" },
            { id: "manual", label: "Enter manually" },
          ]}
          active={mode}
          onChange={setMode}
        />
      </div>

      {mode === "manual" ? (
        <form onSubmit={submitManual} className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="University">
              <input
                className={cls}
                value={university}
                onChange={(e) => setUniversity(e.target.value)}
                required
              />
            </Field>
          </div>
          <Field label="Department">
            <input
              className={cls}
              placeholder="e.g. Computer Science"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            />
          </Field>
          <Field label="Degree">
            <input
              className={cls}
              placeholder="e.g. PhD"
              value={degree}
              onChange={(e) => setDegree(e.target.value)}
            />
          </Field>
          <Field label="Program site">
            <input
              className={cls}
              type="url"
              placeholder="https://cs.example.edu/phd"
              value={portalUrl}
              onChange={(e) => setPortalUrl(e.target.value)}
            />
          </Field>
          <Field label="Application portal">
            <input
              className={cls}
              type="url"
              placeholder="https://apply.example.edu/"
              value={applicationUrl}
              onChange={(e) => setApplicationUrl(e.target.value)}
            />
          </Field>
          <Field label="Admissions email">
            <input
              className={cls}
              type="email"
              placeholder="admissions@example.edu"
              value={admissionsEmail}
              onChange={(e) => setAdmissionsEmail(e.target.value)}
            />
          </Field>
          <div className="pt-1 sm:col-span-2">
            <Button variant="primary" type="submit" disabled={busy || !university.trim()}>
              {busy ? "Adding…" : "Add program"}
            </Button>
          </div>
        </form>
      ) : (
        <form onSubmit={submitResearch} className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Field label="University">
            <input
              className={cls}
              value={researchUniversity}
              onChange={(e) => setResearchUniversity(e.target.value)}
              required
            />
          </Field>
          <Field label="Department / program">
            <input
              className={cls}
              placeholder="e.g. Computer Science"
              value={researchDepartment}
              onChange={(e) => setResearchDepartment(e.target.value)}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Official program or department site">
              <input
                className={cls}
                type="url"
                placeholder="https://cs.example.edu/phd"
                value={officialUrl}
                onChange={(e) => setOfficialUrl(e.target.value)}
                required
              />
            </Field>
          </div>
          <p className="text-xs text-ink-subtle sm:col-span-2">
            Claude reads <strong>only</strong> that institution's site and collects public
            program facts, faculty, deadlines and requirements. Everything comes back marked{" "}
            <em>researched</em> and needs your verification.
          </p>
          <div className="pt-1 sm:col-span-2">
            <Button
              variant="primary"
              type="submit"
              disabled={researching || !researchUniversity.trim() || !officialUrl.trim()}
            >
              {researching ? "Researching…" : "Research with Claude"}
            </Button>
          </div>
        </form>
      )}

      {error && <ErrorText>{error}</ErrorText>}
    </div>
  );
}
