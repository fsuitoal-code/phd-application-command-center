// Typed fetch wrappers over the backend /api (Vite proxies /api -> :8000).

import type {
  DashboardOverview,
  Deadline,
  DocType,
  Faculty,
  FacultyNote,
  MyNote,
  ProgramCreate,
  ProgramDetail,
  ProgramNote,
  ProgramStep,
  ProgramSummary,
  Requirement,
  SuggestFacultyResult,
} from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// Empty headers so the browser sets the multipart boundary itself.
function multipart<T>(path: string, method: string, body: FormData): Promise<T> {
  return req<T>(path, { method, body, headers: {} });
}

export const api = {
  listPrograms: () => req<ProgramSummary[]>("/programs"),
  dashboardOverview: () => req<DashboardOverview>("/dashboard/overview"),
  reorderPrograms: (ids: number[]) =>
    req<ProgramSummary[]>("/programs/reorder", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  getProgram: (id: number) => req<ProgramDetail>(`/programs/${id}`),
  createProgram: (body: ProgramCreate) =>
    req<ProgramDetail>("/programs", { method: "POST", body: JSON.stringify(body) }),
  researchProgram: (query: string, officialUrl: string) =>
    req<ProgramDetail>("/programs/research", {
      method: "POST",
      body: JSON.stringify({ query, official_url: officialUrl }),
    }),
  updateProgram: (id: number, body: Partial<ProgramCreate>) =>
    req<ProgramDetail>(`/programs/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteProgram: (id: number) =>
    req<void>(`/programs/${id}`, { method: "DELETE" }),
  addFaculty: (id: number, body: Partial<Faculty> & { name: string }) =>
    req<Faculty>(`/programs/${id}/faculty`, { method: "POST", body: JSON.stringify(body) }),
  addDeadline: (
    id: number,
    body: { type: string; date: string; notes?: string | null },
  ) => req<Deadline>(`/programs/${id}/deadlines`, { method: "POST", body: JSON.stringify(body) }),
  updateDeadline: (
    programId: number,
    deadlineId: number,
    body: { type?: string; date?: string | null; notes?: string | null },
  ) =>
    req<Deadline>(`/programs/${programId}/deadlines/${deadlineId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteDeadline: (programId: number, deadlineId: number) =>
    req<void>(`/programs/${programId}/deadlines/${deadlineId}`, { method: "DELETE" }),
  confirmDeadline: (programId: number, deadlineId: number, date?: string) =>
    req<Deadline>(`/programs/${programId}/deadlines/${deadlineId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ date: date ?? null }),
    }),
  reorderDeadlines: (programId: number, ids: number[]) =>
    req<Deadline[]>(`/programs/${programId}/deadlines/reorder`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  reorderFaculty: (programId: number, ids: number[]) =>
    req<Faculty[]>(`/programs/${programId}/faculty/reorder`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  addRequirement: (
    id: number,
    body: {
      kind: string;
      value?: string | null;
      source?: string;
      needs_human_verification?: boolean;
    },
  ) =>
    req<Requirement>(`/programs/${id}/requirements`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateRequirement: (
    programId: number,
    reqId: number,
    body: { kind?: string; value?: string | null },
  ) =>
    req<Requirement>(`/programs/${programId}/requirements/${reqId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteRequirement: (programId: number, reqId: number) =>
    req<void>(`/programs/${programId}/requirements/${reqId}`, { method: "DELETE" }),
  reorderRequirements: (programId: number, ids: number[]) =>
    req<Requirement[]>(`/programs/${programId}/requirements/reorder`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),

  addNote: (id: number, body: { text: string }) =>
    req<ProgramNote>(`/programs/${id}/notes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateNote: (programId: number, noteId: number, body: { text?: string }) =>
    req<ProgramNote>(`/programs/${programId}/notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteNote: (programId: number, noteId: number) =>
    req<void>(`/programs/${programId}/notes/${noteId}`, { method: "DELETE" }),
  reorderNotes: (programId: number, ids: number[]) =>
    req<ProgramNote[]>(`/programs/${programId}/notes/reorder`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  confirmNote: (programId: number, noteId: number, text?: string) =>
    req<ProgramNote>(`/programs/${programId}/notes/${noteId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ text: text ?? null }),
    }),

  // ── Faculty actions ──
  /** A billed web pass: minutes, not seconds. */
  researchFaculty: (facultyId: number) =>
    req<Faculty>(`/faculty/${facultyId}/research`, { method: "POST" }),
  deleteFaculty: (facultyId: number) =>
    req<void>(`/faculty/${facultyId}`, { method: "DELETE" }),
  suggestFaculty: (programId: number, officialUrl?: string) =>
    req<SuggestFacultyResult>(`/programs/${programId}/suggest-faculty`, {
      method: "POST",
      body: JSON.stringify({ official_url: officialUrl ?? null }),
    }),

  addFacultyNote: (facultyId: number, body: { text: string }) =>
    req<FacultyNote>(`/faculty/${facultyId}/notes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateFacultyNote: (facultyId: number, noteId: number, body: { text: string }) =>
    req<FacultyNote>(`/faculty/${facultyId}/notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteFacultyNote: (facultyId: number, noteId: number) =>
    req<void>(`/faculty/${facultyId}/notes/${noteId}`, { method: "DELETE" }),
  reorderFacultyNotes: (facultyId: number, ids: number[]) =>
    req<FacultyNote[]>(`/faculty/${facultyId}/notes/reorder`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),

  // ── My Docs (per program) ──
  getDocs: (programId: number) => req<DocType[]>(`/programs/${programId}/docs`),
  addDocType: (programId: number, title: string) =>
    req<DocType>(`/programs/${programId}/docs`, {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  renameDocType: (id: number, title: string) =>
    req<DocType>(`/docs/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  deleteDocType: (id: number) => req<void>(`/docs/${id}`, { method: "DELETE" }),
  /** Where the browser can open an uploaded file. */
  docFileUrl: (id: number) => `/api/docs/files/${id}`,
  // Multipart: the browser must set its own boundary, so this one call skips
  // the JSON content-type header `req` sends.
  uploadDocFile: async (programId: number, docTypeId: number, file: File) => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`/api/programs/${programId}/docs/${docTypeId}/files`, {
      method: "POST",
      body,
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const payload = await res.json();
        if (payload?.detail)
          detail =
            typeof payload.detail === "string"
              ? payload.detail
              : JSON.stringify(payload.detail);
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return await res.json();
  },
  deleteDocFile: (id: number) => req<void>(`/docs/files/${id}`, { method: "DELETE" }),

  // ── My Notes ──
  addMyNote: (
    programId: number,
    note: { text: string; link_url: string | null; due_date: string | null; file: File | null },
  ) => {
    const body = new FormData();
    body.append("text", note.text);
    if (note.link_url) body.append("link_url", note.link_url);
    if (note.due_date) body.append("due_date", note.due_date);
    if (note.file) body.append("file", note.file);
    return multipart<MyNote>(`/programs/${programId}/my-notes`, "POST", body);
  },
  updateMyNote: (
    programId: number,
    noteId: number,
    body: { text?: string; link_url?: string | null; due_date?: string | null },
  ) =>
    req<MyNote>(`/programs/${programId}/my-notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  replaceMyNoteFile: (programId: number, noteId: number, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return multipart<MyNote>(`/programs/${programId}/my-notes/${noteId}/file`, "PUT", body);
  },
  removeMyNoteFile: (programId: number, noteId: number) =>
    req<MyNote>(`/programs/${programId}/my-notes/${noteId}/file`, { method: "DELETE" }),
  myNoteFileUrl: (programId: number, noteId: number) =>
    `/api/programs/${programId}/my-notes/${noteId}/file`,
  deleteMyNote: (programId: number, noteId: number) =>
    req<void>(`/programs/${programId}/my-notes/${noteId}`, { method: "DELETE" }),
  reorderMyNotes: (programId: number, ids: number[]) =>
    req<MyNote[]>(`/programs/${programId}/my-notes/reorder`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),

  setStep: (programId: number, stepId: number, completed: boolean) =>
    req<ProgramStep>(`/programs/${programId}/steps/${stepId}`, {
      method: "PATCH",
      body: JSON.stringify({ completed }),
    }),
  renameStep: (programId: number, stepId: number, label: string) =>
    req<ProgramStep>(`/programs/${programId}/steps/${stepId}`, {
      method: "PATCH",
      body: JSON.stringify({ label }),
    }),
  addStep: (programId: number, label: string) =>
    req<ProgramStep>(`/programs/${programId}/steps`, {
      method: "POST",
      body: JSON.stringify({ label }),
    }),
  deleteStep: (programId: number, stepId: number) =>
    req<void>(`/programs/${programId}/steps/${stepId}`, { method: "DELETE" }),
  reorderSteps: (programId: number, ids: number[]) =>
    req<ProgramStep[]>(`/programs/${programId}/steps/reorder`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  confirmRequirement: (programId: number, reqId: number, value?: string) =>
    req<Requirement>(`/programs/${programId}/requirements/${reqId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ value: value ?? null }),
    }),
};
