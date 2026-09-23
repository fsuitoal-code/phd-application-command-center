"""Program CRUD and sub-resource creation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import insights
from app.db import get_session
from app.models import (
    Deadline,
    Faculty,
    MyNote,
    Program,
    ProgramNote,
    ProgramStep,
    Requirement,
)
from app.models.common import utcnow
from app.models.enums import BUILTIN_REQUIREMENT_KINDS, BUILTIN_STEPS
from app.models.enums import RequirementKind, RequirementSource
from app.schemas import (
    DeadlineConfirm,
    DeadlineCreate,
    DeadlineOut,
    DeadlineReorderRequest,
    DeadlineUpdate,
    FacultyCreate,
    FacultyOut,
    FacultyReorderRequest,
    ProgramCreate,
    ProgramDetail,
    ProgramNoteConfirm,
    ProgramNoteCreate,
    ProgramNoteOut,
    ProgramNoteReorderRequest,
    ProgramNoteUpdate,
    ProgramSummary,
    ProgramUpdate,
    ReorderRequest,
    RequirementConfirm,
    RequirementCreate,
    RequirementOut,
    RequirementReorderRequest,
    RequirementSnapshot,
    RequirementUpdate,
    ProgramStepOut,
    ResearchRequest,
    StepCreate,
    StepReorderRequest,
    StepUpdate,
)

router = APIRouter(prefix="/api/programs", tags=["programs"])


def ensure_steps(session: Session, program_id: int) -> None:
    """Materialise the built-in application steps for a program.

    No-op when the program already has rows, so it is safe to call on every
    detail load — that is what carries programs created before the steps table
    existed, alongside the migration's backfill.
    """
    existing = session.scalar(
        select(func.count())
        .select_from(ProgramStep)
        .where(ProgramStep.program_id == program_id)
    )
    if existing:
        return
    for order, (key, label) in enumerate(BUILTIN_STEPS):
        session.add(
            ProgramStep(program_id=program_id, key=key, label=label, sort_order=order)
        )
    session.commit()


def _load_program(session: Session, program_id: int) -> Program:
    """Fetch a program with all children eagerly loaded, or 404."""
    if session.get(Program, program_id) is not None:
        ensure_steps(session, program_id)
    program = session.scalars(
        select(Program)
        .where(Program.id == program_id)
        .options(
            selectinload(Program.faculty).selectinload(Faculty.notes),
            selectinload(Program.deadlines),
            selectinload(Program.requirements),
            selectinload(Program.notes),
            selectinload(Program.my_notes),
            selectinload(Program.steps),
        )
    ).first()
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


def _safe_date(value: str) -> date | None:
    """Parse an ISO date string from research output; None if malformed."""
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def _application_deadline(program: Program) -> Deadline | None:
    """The program's Application-type deadline — always present, per
    ``_ensure_application_deadline``, though its date may still be null.

    Prefers a dated one (soonest, if more than one somehow exists) over the
    blank placeholder, so a deadline added without going through the
    in-place edit flow (e.g. a second "application"-typed row) still counts."""
    candidates = [d for d in program.deadlines if d.type.strip().lower() == "application"]
    dated = [d for d in candidates if d.date is not None]
    if dated:
        return min(dated, key=lambda d: d.date)
    return candidates[0] if candidates else None


def _next_sort_order(session: Session) -> int:
    """Append position for a new program — the end of the manual order."""
    highest = session.scalar(select(func.max(Program.sort_order)))
    return 0 if highest is None else highest + 1


def _ensure_application_deadline(program: Program) -> None:
    """Every new program gets an Application deadline, even with no known
    date yet — a research pass that didn't find one, or a program added by
    hand with none at all. Shows as "No deadline" until the user fills one
    in (Deadline.date is nullable for exactly this)."""
    if any(d.type.strip().lower() == "application" for d in program.deadlines):
        return
    program.deadlines.append(
        Deadline(
            type="application",
            date=None,
            sort_order=len(program.deadlines),
            source=RequirementSource.CONFIRMED_BY_PROGRAM.value,
            needs_human_verification=False,
        )
    )


def _ensure_default_requirements(program: Program) -> None:
    """Every new program gets all six built-in requirement fields (GRE,
    TOEFL, Application Fee, Fee Waiver, Recommendation Letters, Essay Type),
    blank and flagged for verification when nothing was found for them —
    same "always present, even empty" idea as _ensure_application_deadline.
    Only fills in kinds not already present, so a research pass's findings
    are never duplicated as blanks."""
    existing_kinds = {r.kind.strip().lower() for r in program.requirements}
    for kind in BUILTIN_REQUIREMENT_KINDS:
        if kind in existing_kinds:
            continue
        program.requirements.append(
            Requirement(
                kind=kind,
                value=None,
                source=RequirementSource.RESEARCHED.value,
                needs_human_verification=True,
                sort_order=len(program.requirements),
            )
        )


def _merge_researched_requirements(program: Program, found: list) -> None:
    """Write a research pass's found requirements onto a fresh program,
    keeping the six built-in kinds in their fixed display order (blank when
    the pass found nothing for one) regardless of what order Claude returned
    them in, then appending anything else it found (e.g. "other") after."""
    found_by_kind: dict[str, object] = {}
    extra: list = []
    for r in found:
        key = r.kind.strip().lower()
        if key in BUILTIN_REQUIREMENT_KINDS and key not in found_by_kind:
            found_by_kind[key] = r
        else:
            extra.append(r)

    for kind in BUILTIN_REQUIREMENT_KINDS:
        match = found_by_kind.get(kind)
        program.requirements.append(
            Requirement(
                kind=kind,
                value=match.value if match else None,
                source=RequirementSource.RESEARCHED.value,
                needs_human_verification=True,
                sort_order=len(program.requirements),
            )
        )
    for r in extra:
        program.requirements.append(
            Requirement(
                kind=r.kind,
                value=r.value,
                source=RequirementSource.RESEARCHED.value,
                needs_human_verification=True,
                sort_order=len(program.requirements),
            )
        )


def _requirement_snapshot(program: Program, kind: str) -> RequirementSnapshot | None:
    """The most recently added row for a requirement kind (a program should
    only ever have one per built-in kind, but a snapshot picks a definite
    answer rather than erroring if a duplicate ever exists), or None when the
    kind hasn't been recorded — distinct from a recorded-but-blank value."""
    match = next((r for r in program.requirements if r.kind.strip().lower() == kind), None)
    if match is None:
        return None
    return RequirementSnapshot(
        value=match.value,
        source=match.source,
        needs_human_verification=match.needs_human_verification,
    )


def _summary(program: Program) -> ProgramSummary:
    app_deadline = _application_deadline(program)
    app_date = app_deadline.date if app_deadline else None
    urgency, days_until = insights.urgency_for(app_date)
    return ProgramSummary(
        id=program.id,
        university=program.university,
        department=program.department,
        degree=program.degree,
        portal_url=program.portal_url,
        date_added=program.date_added,
        application_deadline=app_date,
        faculty_count=len(program.faculty),
        sort_order=program.sort_order,
        steps_completed=sum(1 for s in program.steps if s.completed),
        steps_total=len(program.steps),
        days_until_deadline=days_until,
        urgency=urgency,
        last_activity=insights.last_activity_of(program),
        is_stale=insights.is_stale(program, app_date),
        gre=_requirement_snapshot(program, RequirementKind.GRE.value),
        toefl=_requirement_snapshot(program, RequirementKind.TOEFL.value),
        app_fee=_requirement_snapshot(program, RequirementKind.APP_FEE.value),
    )


def _all_enriched(session: Session) -> list[ProgramSummary]:
    """Load every program with the relationships needed for enrichment."""
    programs = session.scalars(
        select(Program).options(
            selectinload(Program.deadlines),
            selectinload(Program.faculty),
            selectinload(Program.steps),
            selectinload(Program.my_notes),
            selectinload(Program.requirements),
        )
    ).all()
    return [_summary(p) for p in programs]


@router.get("", response_model=list[ProgramSummary])
def list_programs(session: Session = Depends(get_session)) -> list[ProgramSummary]:
    """The user's own order, set by dragging rows on the main page.

    Deadline urgency is still surfaced per row (``urgency``, ``days_until_deadline``,
    ``is_stale``) and drives the dashboard — it just no longer decides the order.
    """
    summaries = _all_enriched(session)
    summaries.sort(key=lambda s: (s.sort_order, s.id))
    return summaries


@router.post("/reorder", response_model=list[ProgramSummary])
def reorder_programs(
    payload: ReorderRequest, session: Session = Depends(get_session)
) -> list[ProgramSummary]:
    """Persist the manual ordering: each program's sort_order becomes its index.

    Declared before the ``/{program_id}`` routes so the literal path wins.

    The payload must be exactly the set of existing program ids. Accepting a
    partial list would let a stale page (one opened before a program was added
    or deleted) silently reorder everything around missing rows.
    """
    existing = {p.id: p for p in session.scalars(select(Program)).all()}
    if sorted(payload.ids) != sorted(existing):
        raise HTTPException(
            status_code=400,
            detail="Reorder must list every program exactly once; reload and retry",
        )
    for index, pid in enumerate(payload.ids):
        existing[pid].sort_order = index
    session.commit()
    summaries = _all_enriched(session)
    summaries.sort(key=lambda s: (s.sort_order, s.id))
    return summaries


@router.post("/research", response_model=ProgramDetail, status_code=201)
async def research_program_endpoint(
    payload: ResearchRequest, session: Session = Depends(get_session)
) -> ProgramDetail:
    """Rule 3/8 flow: Claude reads the pasted official URL's domain and writes
    a new program with researched, unverified facts."""
    from app.claude.research import quote_fragment_url, research_program
    from app.config import ClaudeTask, settings

    try:
        found = await research_program(payload.query, payload.official_url)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Research failed: {exc}") from exc

    program = Program(
        university=found.university,
        department=found.department,
        degree=found.degree,
        portal_url=found.portal_url or payload.official_url,
        # Provenance, per Rule 8: the config says what a pass WOULD use today,
        # which is not the same question as what produced these facts.
        research_model=settings.model_for(ClaudeTask.RESEARCH_SYNTHESIS),
        sort_order=_next_sort_order(session),
    )
    for order, f in enumerate(found.faculty):
        program.faculty.append(
            Faculty(
                name=f.name,
                research_areas=f.research_areas,
                homepage_url=f.homepage_url,
                sort_order=order,
            )
        )
    # Seed the initial manual order by date — a sensible starting point the
    # user can then drag to rearrange, same idea as the programs.sort_order
    # migration backfill.
    parsed_deadlines = [(d, _safe_date(d.date)) for d in found.deadlines]
    parsed_deadlines = [(d, p) for d, p in parsed_deadlines if p is not None]
    parsed_deadlines.sort(key=lambda pair: pair[1])
    for order, (d, parsed) in enumerate(parsed_deadlines):
        program.deadlines.append(
            Deadline(
                type=d.type,
                date=parsed,
                notes=d.notes,
                sort_order=order,
                source=RequirementSource.RESEARCHED.value,
                needs_human_verification=True,
            )
        )
    _ensure_application_deadline(program)
    _merge_researched_requirements(program, found.requirements)
    for order, n in enumerate(found.notes):
        program.notes.append(
            ProgramNote(
                text=n.text,
                quote=n.quote,
                source_url=quote_fragment_url(n.source_url, n.quote),
                source_label=n.source_label,
                source=RequirementSource.RESEARCHED.value,
                needs_human_verification=True,
                sort_order=order,
            )
        )

    session.add(program)
    session.commit()
    return _load_program(session, program.id)


@router.post("", response_model=ProgramDetail, status_code=201)
def create_program(
    payload: ProgramCreate, session: Session = Depends(get_session)
) -> ProgramDetail:
    program = Program(
        **payload.model_dump(exclude_unset=False),
        sort_order=_next_sort_order(session),
    )
    _ensure_application_deadline(program)
    _ensure_default_requirements(program)
    session.add(program)
    session.commit()
    return _load_program(session, program.id)


@router.get("/{program_id}", response_model=ProgramDetail)
def get_program(
    program_id: int, session: Session = Depends(get_session)
) -> ProgramDetail:
    return _load_program(session, program_id)


@router.patch("/{program_id}", response_model=ProgramDetail)
def update_program(
    program_id: int,
    payload: ProgramUpdate,
    session: Session = Depends(get_session),
) -> ProgramDetail:
    program = _load_program(session, program_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(program, field, value)
    session.commit()
    return _load_program(session, program_id)


@router.delete("/{program_id}", status_code=204)
def delete_program(program_id: int, session: Session = Depends(get_session)) -> None:
    program = session.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    for note in session.scalars(
        select(MyNote).where(MyNote.program_id == program_id, MyNote.file_path.is_not(None))
    ):
        Path(note.file_path).unlink(missing_ok=True)
    session.delete(program)  # cascades to children (ORM + DB FK)
    session.commit()


# ── Manual sub-resource creation ──────────────────────────────────────────
@router.post("/{program_id}/faculty", response_model=FacultyOut, status_code=201)
def add_faculty(
    program_id: int,
    payload: FacultyCreate,
    session: Session = Depends(get_session),
) -> Faculty:
    _load_program(session, program_id)  # 404 if missing
    highest = session.scalar(
        select(func.max(Faculty.sort_order)).where(Faculty.program_id == program_id)
    )
    faculty = Faculty(
        program_id=program_id, sort_order=(highest or 0) + 1, **payload.model_dump()
    )
    session.add(faculty)
    session.commit()
    session.refresh(faculty)
    return faculty


@router.post("/{program_id}/faculty/reorder", response_model=list[FacultyOut])
def reorder_faculty(
    program_id: int,
    payload: FacultyReorderRequest,
    session: Session = Depends(get_session),
) -> list[Faculty]:
    """Persist the manual ordering of one program's faculty -- same defensive
    full-set check as the deadline/requirement/note/step reorders, for the
    same reason: a stale page shouldn't silently reorder everything around a
    faculty member added or removed elsewhere."""
    _load_program(session, program_id)
    existing = {
        f.id: f
        for f in session.scalars(
            select(Faculty).where(Faculty.program_id == program_id)
        ).all()
    }
    if sorted(payload.ids) != sorted(existing):
        raise HTTPException(
            status_code=400,
            detail="Reorder must list every faculty member exactly once; reload and retry",
        )
    for index, fid in enumerate(payload.ids):
        existing[fid].sort_order = index
    session.commit()
    faculty = session.scalars(
        select(Faculty)
        .where(Faculty.program_id == program_id)
        .order_by(Faculty.sort_order)
    ).all()
    return list(faculty)


@router.post("/{program_id}/deadlines", response_model=DeadlineOut, status_code=201)
def add_deadline(
    program_id: int,
    payload: DeadlineCreate,
    session: Session = Depends(get_session),
) -> Deadline:
    _load_program(session, program_id)
    data = payload.model_dump()
    data["type"] = data["type"].strip() or "application"
    if hasattr(data["source"], "value"):
        data["source"] = data["source"].value
    highest = session.scalar(
        select(func.max(Deadline.sort_order)).where(Deadline.program_id == program_id)
    )
    deadline = Deadline(program_id=program_id, sort_order=(highest or 0) + 1, **data)
    session.add(deadline)
    session.commit()
    session.refresh(deadline)
    return deadline


def _load_deadline(session: Session, program_id: int, deadline_id: int) -> Deadline:
    deadline = session.get(Deadline, deadline_id)
    if deadline is None or deadline.program_id != program_id:
        raise HTTPException(status_code=404, detail="Deadline not found")
    return deadline


@router.patch("/{program_id}/deadlines/{deadline_id}", response_model=DeadlineOut)
def set_deadline(
    program_id: int,
    deadline_id: int,
    payload: DeadlineUpdate,
    session: Session = Depends(get_session),
) -> Deadline:
    """Edit a deadline's type/date/notes. Uses exclude_unset, same as
    update_program, so a field left out of the request is untouched but
    notes can still be explicitly cleared with notes: null.

    Editing type or date is the user asserting the fact themselves, so it
    auto-confirms the same way editing a requirement does -- unless the
    caller explicitly set source/needs_human_verification in the same
    request, which wins instead.
    """
    deadline = _load_deadline(session, program_id, deadline_id)
    fields = payload.model_dump(exclude_unset=True)
    for field, value in fields.items():
        if field == "type":
            value = value.strip()
            if not value:
                raise HTTPException(status_code=400, detail="Deadline needs a type")
        elif field == "source" and hasattr(value, "value"):
            value = value.value
        setattr(deadline, field, value)
    if ("type" in fields or "date" in fields) and "source" not in fields:
        deadline.source = RequirementSource.CONFIRMED_BY_PROGRAM.value
        deadline.needs_human_verification = False
    session.commit()
    session.refresh(deadline)
    return deadline


@router.post("/{program_id}/deadlines/{deadline_id}/confirm", response_model=DeadlineOut)
def confirm_deadline(
    program_id: int,
    deadline_id: int,
    payload: DeadlineConfirm,
    session: Session = Depends(get_session),
) -> Deadline:
    """Rule 8: promote a researched deadline to confirmed_by_program.

    Clears needs_human_verification and optionally corrects the date.
    """
    deadline = _load_deadline(session, program_id, deadline_id)
    deadline.source = RequirementSource.CONFIRMED_BY_PROGRAM.value
    deadline.needs_human_verification = False
    if payload.date is not None:
        deadline.date = payload.date
    session.commit()
    session.refresh(deadline)
    return deadline


@router.post("/{program_id}/deadlines/reorder", response_model=list[DeadlineOut])
def reorder_deadlines(
    program_id: int,
    payload: DeadlineReorderRequest,
    session: Session = Depends(get_session),
) -> list[Deadline]:
    """Persist the manual ordering of one program's deadlines — same defensive
    full-set check as the step/program reorders, for the same reason: a stale
    page shouldn't silently reorder everything around a deadline added or
    removed elsewhere."""
    _load_program(session, program_id)
    existing = {
        d.id: d
        for d in session.scalars(
            select(Deadline).where(Deadline.program_id == program_id)
        ).all()
    }
    if sorted(payload.ids) != sorted(existing):
        raise HTTPException(
            status_code=400,
            detail="Reorder must list every deadline exactly once; reload and retry",
        )
    for index, did in enumerate(payload.ids):
        existing[did].sort_order = index
    session.commit()
    deadlines = session.scalars(
        select(Deadline)
        .where(Deadline.program_id == program_id)
        .order_by(Deadline.sort_order)
    ).all()
    return list(deadlines)


@router.delete("/{program_id}/deadlines/{deadline_id}", status_code=204)
def delete_deadline(
    program_id: int, deadline_id: int, session: Session = Depends(get_session)
) -> None:
    deadline = _load_deadline(session, program_id, deadline_id)
    session.delete(deadline)
    session.commit()


@router.post("/{program_id}/requirements", response_model=RequirementOut, status_code=201)
def add_requirement(
    program_id: int,
    payload: RequirementCreate,
    session: Session = Depends(get_session),
) -> Requirement:
    _load_program(session, program_id)
    data = payload.model_dump()
    data["kind"] = data["kind"].strip() or "other"
    if hasattr(data["source"], "value"):
        data["source"] = data["source"].value
    highest = session.scalar(
        select(func.max(Requirement.sort_order)).where(
            Requirement.program_id == program_id
        )
    )
    requirement = Requirement(
        program_id=program_id, sort_order=(highest or 0) + 1, **data
    )
    session.add(requirement)
    session.commit()
    session.refresh(requirement)
    return requirement


def _load_requirement(session: Session, program_id: int, req_id: int) -> Requirement:
    requirement = session.get(Requirement, req_id)
    if requirement is None or requirement.program_id != program_id:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


@router.patch("/{program_id}/requirements/{req_id}", response_model=RequirementOut)
def set_requirement(
    program_id: int,
    req_id: int,
    payload: RequirementUpdate,
    session: Session = Depends(get_session),
) -> Requirement:
    """Edit a requirement's kind/value/source/verification flag. Uses
    exclude_unset, same as set_deadline, so a field left out of the request
    is untouched but value can still be explicitly cleared with value: null.

    Editing kind or value is the user asserting the fact themselves, so it
    auto-confirms the requirement the same way the one-click confirm button
    does -- unless the caller explicitly set source/needs_human_verification
    in the same request, which wins instead.
    """
    requirement = _load_requirement(session, program_id, req_id)
    fields = payload.model_dump(exclude_unset=True)
    for field, value in fields.items():
        if field == "kind":
            value = value.strip()
            if not value:
                raise HTTPException(status_code=400, detail="Requirement needs a kind")
        elif field == "source" and hasattr(value, "value"):
            value = value.value
        setattr(requirement, field, value)
    if ("kind" in fields or "value" in fields) and "source" not in fields:
        requirement.source = RequirementSource.CONFIRMED_BY_PROGRAM.value
        requirement.needs_human_verification = False
    session.commit()
    session.refresh(requirement)
    return requirement


@router.post(
    "/{program_id}/requirements/reorder", response_model=list[RequirementOut]
)
def reorder_requirements(
    program_id: int,
    payload: RequirementReorderRequest,
    session: Session = Depends(get_session),
) -> list[Requirement]:
    """Persist the manual ordering of one program's requirements — same
    defensive full-set check as the deadline/step/program reorders."""
    _load_program(session, program_id)
    existing = {
        r.id: r
        for r in session.scalars(
            select(Requirement).where(Requirement.program_id == program_id)
        ).all()
    }
    if sorted(payload.ids) != sorted(existing):
        raise HTTPException(
            status_code=400,
            detail="Reorder must list every requirement exactly once; reload and retry",
        )
    for index, rid in enumerate(payload.ids):
        existing[rid].sort_order = index
    session.commit()
    requirements = session.scalars(
        select(Requirement)
        .where(Requirement.program_id == program_id)
        .order_by(Requirement.sort_order)
    ).all()
    return list(requirements)


@router.delete("/{program_id}/requirements/{req_id}", status_code=204)
def delete_requirement(
    program_id: int, req_id: int, session: Session = Depends(get_session)
) -> None:
    requirement = _load_requirement(session, program_id, req_id)
    session.delete(requirement)
    session.commit()


@router.post(
    "/{program_id}/requirements/{req_id}/confirm", response_model=RequirementOut
)
def confirm_requirement(
    program_id: int,
    req_id: int,
    payload: RequirementConfirm,
    session: Session = Depends(get_session),
) -> Requirement:
    """Rule 8: promote a researched requirement to confirmed_by_program.

    A manual one-click confirm. Clears needs_human_verification and optionally
    updates the value.
    """
    requirement = session.get(Requirement, req_id)
    if requirement is None or requirement.program_id != program_id:
        raise HTTPException(status_code=404, detail="Requirement not found")
    requirement.source = RequirementSource.CONFIRMED_BY_PROGRAM.value
    requirement.needs_human_verification = False
    if payload.value is not None:
        requirement.value = payload.value
    session.commit()
    session.refresh(requirement)
    return requirement


# ── Notes ──────────────────────────────────────────────────────────────────
@router.post("/{program_id}/notes", response_model=ProgramNoteOut, status_code=201)
def add_note(
    program_id: int,
    payload: ProgramNoteCreate,
    session: Session = Depends(get_session),
) -> ProgramNote:
    """Add a note by hand -- no citation fields, so it's already confirmed
    (see ProgramNoteCreate's defaults, same reasoning as RequirementCreate)."""
    _load_program(session, program_id)
    data = payload.model_dump()
    data["text"] = data["text"].strip()
    if not data["text"]:
        raise HTTPException(status_code=400, detail="Note needs text")
    if hasattr(data["source"], "value"):
        data["source"] = data["source"].value
    highest = session.scalar(
        select(func.max(ProgramNote.sort_order)).where(
            ProgramNote.program_id == program_id
        )
    )
    note = ProgramNote(program_id=program_id, sort_order=(highest or 0) + 1, **data)
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


def _load_note(session: Session, program_id: int, note_id: int) -> ProgramNote:
    note = session.get(ProgramNote, note_id)
    if note is None or note.program_id != program_id:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.patch("/{program_id}/notes/{note_id}", response_model=ProgramNoteOut)
def set_note(
    program_id: int,
    note_id: int,
    payload: ProgramNoteUpdate,
    session: Session = Depends(get_session),
) -> ProgramNote:
    """Edit a note's text. The citation fields (quote/source_url/source_label)
    aren't user-editable -- they're the record of what the source said, not
    something to correct. Editing text auto-confirms, same as a requirement's
    value, unless the caller explicitly passes its own source."""
    note = _load_note(session, program_id, note_id)
    fields = payload.model_dump(exclude_unset=True)
    for field, value in fields.items():
        if field == "text":
            value = value.strip()
            if not value:
                raise HTTPException(status_code=400, detail="Note needs text")
        elif field == "source" and hasattr(value, "value"):
            value = value.value
        setattr(note, field, value)
    if "text" in fields and "source" not in fields:
        note.source = RequirementSource.CONFIRMED_BY_PROGRAM.value
        note.needs_human_verification = False
    session.commit()
    session.refresh(note)
    return note


@router.post("/{program_id}/notes/reorder", response_model=list[ProgramNoteOut])
def reorder_notes(
    program_id: int,
    payload: ProgramNoteReorderRequest,
    session: Session = Depends(get_session),
) -> list[ProgramNote]:
    """Persist the manual ordering of one program's notes — same defensive
    full-set check as the deadline/requirement/step reorders."""
    _load_program(session, program_id)
    existing = {
        n.id: n
        for n in session.scalars(
            select(ProgramNote).where(ProgramNote.program_id == program_id)
        ).all()
    }
    if sorted(payload.ids) != sorted(existing):
        raise HTTPException(
            status_code=400,
            detail="Reorder must list every note exactly once; reload and retry",
        )
    for index, nid in enumerate(payload.ids):
        existing[nid].sort_order = index
    session.commit()
    notes = session.scalars(
        select(ProgramNote)
        .where(ProgramNote.program_id == program_id)
        .order_by(ProgramNote.sort_order)
    ).all()
    return list(notes)


@router.delete("/{program_id}/notes/{note_id}", status_code=204)
def delete_note(
    program_id: int, note_id: int, session: Session = Depends(get_session)
) -> None:
    note = _load_note(session, program_id, note_id)
    session.delete(note)
    session.commit()


@router.post("/{program_id}/notes/{note_id}/confirm", response_model=ProgramNoteOut)
def confirm_note(
    program_id: int,
    note_id: int,
    payload: ProgramNoteConfirm,
    session: Session = Depends(get_session),
) -> ProgramNote:
    """Rule 8: promote a researched note to confirmed_by_program.

    Clears needs_human_verification and optionally corrects the text.
    """
    note = _load_note(session, program_id, note_id)
    note.source = RequirementSource.CONFIRMED_BY_PROGRAM.value
    note.needs_human_verification = False
    if payload.text is not None:
        note.text = payload.text
    session.commit()
    session.refresh(note)
    return note


# ── Application steps ─────────────────────────────────────────────────────
def _load_step(session: Session, program_id: int, step_id: int) -> ProgramStep:
    step = session.get(ProgramStep, step_id)
    if step is None or step.program_id != program_id:
        raise HTTPException(status_code=404, detail="Step not found")
    return step


@router.patch("/{program_id}/steps/{step_id}", response_model=ProgramStepOut)
def set_step(
    program_id: int,
    step_id: int,
    payload: StepUpdate,
    session: Session = Depends(get_session),
) -> ProgramStep:
    """Tick/untick and/or rename a step — built-in or custom, either field
    optional so a completion toggle never touches the label and vice versa.
    Completion is only ever set here, by the user."""
    step = _load_step(session, program_id, step_id)
    if payload.completed is not None:
        step.completed = payload.completed
        step.completed_at = utcnow() if payload.completed else None
    if payload.label is not None:
        label = payload.label.strip()
        if not label:
            raise HTTPException(status_code=400, detail="Step needs a label")
        step.label = label
    session.commit()
    session.refresh(step)
    return step


@router.post("/{program_id}/steps", response_model=ProgramStepOut, status_code=201)
def add_step(
    program_id: int,
    payload: StepCreate,
    session: Session = Depends(get_session),
) -> ProgramStep:
    """Append a custom step to one program (a writing sample, a portfolio…)."""
    _load_program(session, program_id)
    label = payload.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="Step needs a label")
    highest = session.scalar(
        select(func.max(ProgramStep.sort_order)).where(
            ProgramStep.program_id == program_id
        )
    )
    step = ProgramStep(
        program_id=program_id,
        key=f"custom_{label.lower().replace(' ', '_')[:40]}",
        label=label,
        sort_order=(highest or 0) + 1,
        is_custom=True,
    )
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


@router.post("/{program_id}/steps/reorder", response_model=list[ProgramStepOut])
def reorder_steps(
    program_id: int,
    payload: StepReorderRequest,
    session: Session = Depends(get_session),
) -> list[ProgramStep]:
    """Persist the manual ordering of one program's steps (built-in and custom alike).

    The payload must be exactly the set of that program's existing step ids —
    same defensive check as the program-list reorder, for the same reason: a
    stale page shouldn't silently reorder everything around a step added or
    removed elsewhere.
    """
    _load_program(session, program_id)
    existing = {
        s.id: s
        for s in session.scalars(
            select(ProgramStep).where(ProgramStep.program_id == program_id)
        ).all()
    }
    if sorted(payload.ids) != sorted(existing):
        raise HTTPException(
            status_code=400,
            detail="Reorder must list every step exactly once; reload and retry",
        )
    for index, sid in enumerate(payload.ids):
        existing[sid].sort_order = index
    session.commit()
    steps = session.scalars(
        select(ProgramStep)
        .where(ProgramStep.program_id == program_id)
        .order_by(ProgramStep.sort_order)
    ).all()
    return list(steps)


@router.delete("/{program_id}/steps/{step_id}", status_code=204)
def delete_step(
    program_id: int, step_id: int, session: Session = Depends(get_session)
) -> None:
    """Remove one step, built-in or custom — a program's checklist is fully its
    own from here, not a fixed superset. ``BUILTIN_STEPS`` still seeds every
    *new* program the same way; deleting one here only affects this program.
    """
    step = _load_step(session, program_id, step_id)
    session.delete(step)
    session.commit()
