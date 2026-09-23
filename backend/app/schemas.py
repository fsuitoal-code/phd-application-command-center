"""Pydantic request/response models for the API layer."""

from __future__ import annotations

from datetime import date, datetime

# A field literally named `date` typed `date | None` can't use the bare
# `date` import: Pydantic's Python 3.14 forward-ref eval resolves the
# annotation string in a namespace where the class's own `date` field
# (bound to its default) shadows the `datetime.date` import, so `date | None`
# evaluates as `None | None` and raises. Only the `X | None` form triggers
# eval; a bare `date` annotation doesn't, so only this alias is needed.
from datetime import date as _Date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequirementSource


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Faculty ───────────────────────────────────────────────────────────────
class FacultyCreate(BaseModel):
    name: str
    research_areas: str | None = None
    homepage_url: str | None = None
    contacted: bool = False


class FacultyOut(_ORM):
    id: int
    program_id: int
    name: str
    research_areas: str | None
    homepage_url: str | None
    contacted: bool
    sort_order: int
    dossier: str | None = None
    dossier_model: str | None = None
    dossier_researched_at: datetime | None = None
    notes: list["FacultyNoteOut"] = Field(default_factory=list)


class FacultyReorderRequest(BaseModel):
    """The full list of one program's faculty ids, in their new order."""

    ids: list[int]


# ── Faculty note ─────────────────────────────────────────────────────────
# Purely user-typed, unlike ProgramNote -- no Claude contract writes these, so
# there's no Rule 8 provenance (source/quote/needs_human_verification) here.
class FacultyNoteCreate(BaseModel):
    text: str = Field(min_length=1)


class FacultyNoteUpdate(BaseModel):
    text: str = Field(min_length=1)


class FacultyNoteReorderRequest(BaseModel):
    """The full list of one faculty member's note ids, in their new order."""

    ids: list[int]


class FacultyNoteOut(_ORM):
    id: int
    faculty_id: int
    text: str
    sort_order: int


# ── My Notes ─────────────────────────────────────────────────────────────
# A program's free-form, purely user-typed notes. Creation is multipart (it can
# carry a file), so it has no schema here; the file is swapped via its own
# endpoint. Unset fields are left alone, null clears one.
class MyNoteUpdate(BaseModel):
    text: str | None = None
    link_url: str | None = None
    due_date: date | None = None


class MyNoteReorderRequest(BaseModel):
    """The full list of one program's My Notes ids, in their new order."""

    ids: list[int]


class MyNoteOut(_ORM):
    id: int
    program_id: int
    text: str
    link_url: str | None
    due_date: date | None
    file_name: str | None
    sort_order: int


# ── Deadline ──────────────────────────────────────────────────────────────
# `type` is free text, not a fixed enum: "Application", "Funding", "Rec
# letters by" etc. are common cases, but the user can type any label a
# program's own deadlines call for.
class DeadlineCreate(BaseModel):
    type: str = Field(default="application", max_length=40)
    #: Nullable — a program can be seeded with an Application deadline before
    #: its actual date is known.
    date: _Date | None = None
    notes: str | None = None
    # A deadline added through this endpoint was typed in by the user, so it
    # is already confirmed -- there is nothing to verify. Only the research
    # pass writes source=researched, and it builds Deadline rows directly
    # rather than going through this schema. Same reasoning as
    # RequirementCreate.
    source: RequirementSource = RequirementSource.CONFIRMED_BY_PROGRAM
    needs_human_verification: bool = False


class DeadlineUpdate(BaseModel):
    """Edit a deadline's fields. Whichever field is omitted is left untouched."""

    type: str | None = Field(default=None, max_length=40)
    date: _Date | None = None
    notes: str | None = None
    source: RequirementSource | None = None
    needs_human_verification: bool | None = None


class DeadlineReorderRequest(BaseModel):
    """The full list of one program's deadline ids, in their new order."""

    ids: list[int]


class DeadlineConfirm(BaseModel):
    date: _Date | None = None


class DeadlineOut(_ORM):
    id: int
    program_id: int
    type: str
    date: _Date | None
    notes: str | None
    sort_order: int
    source: str
    needs_human_verification: bool


# ── Requirement ───────────────────────────────────────────────────────────
# `kind` is free text, not a fixed enum, same as Deadline.type: GRE/TOEFL/
# Application Fee/Fee Waiver/Recommendation Letters/Essay Type are the six
# built-in kinds every program is seeded with, but the user can add any
# other kind a program calls for.
class RequirementCreate(BaseModel):
    kind: str = Field(default="other", max_length=40)
    value: str | None = None
    # A requirement added through this endpoint was typed in by the user
    # (the Add-requirement form), so it is already confirmed -- there is nothing to
    # verify. Only an actual research pass writes source=researched, and it
    # builds Requirement rows directly rather than going through this schema.
    source: RequirementSource = RequirementSource.CONFIRMED_BY_PROGRAM
    needs_human_verification: bool = False


class RequirementUpdate(BaseModel):
    """Edit a requirement's fields. Whichever field is omitted is left untouched."""

    kind: str | None = Field(default=None, max_length=40)
    value: str | None = None
    source: RequirementSource | None = None
    needs_human_verification: bool | None = None


class RequirementReorderRequest(BaseModel):
    """The full list of one program's requirement ids, in their new order."""

    ids: list[int]


class RequirementOut(_ORM):
    id: int
    program_id: int
    kind: str
    value: str | None
    source: str
    needs_human_verification: bool
    sort_order: int


# ── Program note ─────────────────────────────────────────────────────────
# One cited fact about a program, individually confirmable (Rule 8). Replaces
# the old single markdown-blob `programs.notes` column.
class ProgramNoteCreate(BaseModel):
    text: str = Field(min_length=1)
    # A hand-added note has no citation -- nothing a research pass found.
    quote: str | None = None
    source_url: str | None = None
    source_label: str | None = None
    # Typed in by the user, so already confirmed -- same reasoning as
    # RequirementCreate. Only the research pass writes source=researched,
    # and it builds ProgramNote rows directly rather than through this schema.
    source: RequirementSource = RequirementSource.CONFIRMED_BY_PROGRAM
    needs_human_verification: bool = False


class ProgramNoteUpdate(BaseModel):
    """Edit a note's text. Whichever field is omitted is left untouched.

    Citation fields (quote/source_url/source_label) aren't included here --
    they're the record of what the source said, not user-editable.
    """

    text: str | None = Field(default=None, min_length=1)
    source: RequirementSource | None = None
    needs_human_verification: bool | None = None


class ProgramNoteReorderRequest(BaseModel):
    """The full list of one program's note ids, in their new order."""

    ids: list[int]


class ProgramNoteConfirm(BaseModel):
    text: str | None = None


class ProgramNoteOut(_ORM):
    id: int
    program_id: int
    text: str
    quote: str | None
    source_url: str | None
    source_label: str | None
    source: str
    needs_human_verification: bool
    sort_order: int


# ── Application steps ─────────────────────────────────────────────────────
class ProgramStepOut(_ORM):
    id: int
    program_id: int
    key: str
    label: str
    completed: bool
    completed_at: datetime | None
    sort_order: int
    is_custom: bool


class StepCreate(BaseModel):
    """A custom step added to one program."""

    label: str


class StepUpdate(BaseModel):
    """Tick/untick and/or rename a step. Completion is always an explicit user
    action; whichever field is omitted is left untouched."""

    completed: bool | None = None
    label: str | None = None


class StepReorderRequest(BaseModel):
    """The full list of one program's step ids, in their new order."""

    ids: list[int]


# ── Program ───────────────────────────────────────────────────────────────
class ProgramCreate(BaseModel):
    university: str = Field(min_length=1)
    department: str | None = None
    degree: str | None = None
    #: The department/program page. `application_url` is where you submit.
    portal_url: str | None = None
    application_url: str | None = None
    admissions_email: str | None = None


class ProgramUpdate(BaseModel):
    university: str | None = Field(default=None, min_length=1)
    department: str | None = None
    degree: str | None = None
    portal_url: str | None = None
    application_url: str | None = None
    admissions_email: str | None = None


class ReorderRequest(BaseModel):
    """The full list of program ids in their new order."""

    ids: list[int]


class RequirementSnapshot(BaseModel):
    """One requirement's value as it stands right now, for a row that just
    needs to show it rather than edit it (the Dashboard table) — same fields
    as RequirementOut, minus the ids a read-only snapshot has no use for."""

    value: str | None = None
    source: str = RequirementSource.RESEARCHED.value
    needs_human_verification: bool = True


class ProgramSummary(_ORM):
    """Row in the main-page list."""

    id: int
    university: str
    department: str | None
    degree: str | None
    portal_url: str | None
    date_added: datetime
    application_deadline: date | None = None
    faculty_count: int = 0
    #: Position in the manual ordering.
    sort_order: int = 0
    #: Checklist completion (program_steps), driving the row's progress bar.
    steps_completed: int = 0
    steps_total: int = 0
    # Deadline urgency and staleness.
    days_until_deadline: int | None = None
    urgency: str = "none"  # overdue | due_soon | upcoming | none
    last_activity: datetime | None = None
    is_stale: bool = False
    #: The three requirement kinds a quick program-comparison cares about
    #: (Dashboard table). None when that kind hasn't been recorded at all.
    gre: RequirementSnapshot | None = None
    toefl: RequirementSnapshot | None = None
    app_fee: RequirementSnapshot | None = None


class DashboardOut(BaseModel):
    overdue: list[ProgramSummary]
    due_soon: list[ProgramSummary]
    stale: list[ProgramSummary]


class AgendaItem(BaseModel):
    """One dated thing on the Dashboard's timeline: a deadline row, or a My Notes
    reminder (``due_date``). A reminder carries no provenance — no Claude
    contract writes one — so ``source`` is None for it."""

    program_id: int
    university: str
    kind: str  # deadline | reminder
    #: A deadline's free-text ``type``, or a reminder's note text.
    label: str
    date: _Date
    source: str | None = None
    needs_human_verification: bool = False


class AttentionItem(BaseModel):
    """One reason a program needs a look, with the tab that fixes it."""

    program_id: int
    university: str
    kind: str  # overdue | stale | no_deadline_date | unverified | missing_requirements
    detail: str
    tab: str  # overview | faculty | docs | notes


class StepColumn(BaseModel):
    key: str
    label: str


class ChecklistRow(BaseModel):
    """A program's built-in steps by key — True/False, or None where the user
    deleted that step — plus its custom steps as a count."""

    program_id: int
    university: str
    steps: dict[str, bool | None]
    custom_done: int
    custom_total: int


class CompareCell(BaseModel):
    """One requirement boiled down for the comparison table: ``text`` is the
    short read ("Required · min 90", "$125"), ``detail`` the full stored value
    for hover. ``text`` is None when nothing is recorded."""

    text: str | None = None
    detail: str | None = None
    source: str = RequirementSource.RESEARCHED.value
    needs_human_verification: bool = True


class CompareRow(BaseModel):
    program_id: int
    gre: CompareCell
    toefl: CompareCell
    app_fee: CompareCell


class DashboardOverview(BaseModel):
    """Everything the Dashboard shows, computed in one read-only pass."""

    #: Manual order, same as the Programs page — the comparison table uses it.
    programs: list[ProgramSummary]
    submitted_count: int
    #: Researched facts with a value that the user hasn't confirmed yet.
    unverified_count: int
    #: Date order, soonest first; past items included (they're overdue).
    agenda: list[AgendaItem]
    attention: list[AttentionItem]
    step_columns: list[StepColumn]
    checklist: list[ChecklistRow]
    #: Same order as ``programs``.
    compare: list[CompareRow]
    #: Sum of the application fees that read as a plain dollar amount.
    fee_total: float
    fee_counted: int
    fee_unknown: int


class ProgramDetail(_ORM):
    id: int
    university: str
    department: str | None
    degree: str | None
    portal_url: str | None
    application_url: str | None = None
    admissions_email: str | None = None
    #: None for a hand-added program, or one researched before this was tracked.
    research_model: str | None = None
    date_added: datetime
    faculty: list[FacultyOut]
    deadlines: list[DeadlineOut]
    requirements: list[RequirementOut]
    notes: list[ProgramNoteOut]
    my_notes: list[MyNoteOut]
    steps: list[ProgramStepOut]


class ResearchRequest(BaseModel):
    """Input to the Claude program-research flow.

    ``official_url`` is required: with general web search disabled, it is the
    seed the flow reads, and fetching is restricted to its domain.
    """

    query: str = Field(min_length=1, description="e.g. 'UW-Madison, Computer Science PhD'")
    official_url: str = Field(
        min_length=1, description="Official program/department URL to read from"
    )


# ── Faculty actions ─────────────────────────────────────────────────────
class SuggestedFacultyOut(BaseModel):
    name: str
    research_areas: str | None = None
    homepage_url: str | None = None


class SuggestFacultyOut(BaseModel):
    faculty: list[SuggestedFacultyOut]
    # Found by the pass but already on the program's list, so not suggested.
    already_listed: list[str]


class SuggestFacultyRequest(BaseModel):
    official_url: str | None = None


# ── My Docs ──────────────────────────────────────────────────────────────
class DocFileOut(_ORM):
    id: int
    doc_type_id: int
    filename: str
    created_at: datetime


class DocTypeOut(_ORM):
    id: int
    program_id: int
    key: str
    title: str
    is_custom: bool
    sort_order: int
    files: list[DocFileOut] = Field(default_factory=list)


class DocTypeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class DocTypeUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class RequirementConfirm(BaseModel):
    value: str | None = None
