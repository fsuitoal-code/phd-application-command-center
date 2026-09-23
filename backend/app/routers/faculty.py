"""Claude-backed faculty actions: research, suggest more.

Endpoints call the ``app.claude.*`` module functions by attribute so tests can
monkeypatch them (no billed calls in tests).

**research** requires no applicant profile. A dossier is about the faculty
member -- what they work on, who is in their group, how students are funded.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.claude import faculty as fac_ai
from app.claude import faculty_dossier as dossier_ai
from app.config import ClaudeTask, settings
from app.db import get_session
from app.models import Faculty, FacultyNote, Program
from app.routers.profile import get_or_create_profile
from app.schemas import (
    FacultyNoteCreate,
    FacultyNoteOut,
    FacultyNoteReorderRequest,
    FacultyNoteUpdate,
    FacultyOut,
    SuggestFacultyOut,
    SuggestFacultyRequest,
)

router = APIRouter(prefix="/api", tags=["faculty-actions"])


def _get_faculty(session: Session, faculty_id: int) -> Faculty:
    faculty = session.get(Faculty, faculty_id)
    if faculty is None:
        raise HTTPException(status_code=404, detail="Faculty not found")
    return faculty


@router.post("/faculty/{faculty_id}/research", response_model=FacultyOut)
async def research_faculty(
    faculty_id: int, session: Session = Depends(get_session)
) -> Faculty:
    """Research one faculty member into a cited, sectioned profile."""
    faculty = _get_faculty(session, faculty_id)
    profile = get_or_create_profile(session)
    program = session.get(Program, faculty.program_id)

    try:
        found = await dossier_ai.research_faculty(profile, faculty, program)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail=f"Faculty research failed: {exc}"
        ) from exc

    markdown = found.to_markdown()
    if not markdown.strip():
        # Every claim failed its quote check, which is the contract working as
        # intended -- but storing the empty result would erase a good earlier
        # dossier and show the user nothing. Say so instead; the slot is spent
        # either way, and they can decide whether to pay for another pass.
        raise HTTPException(
            status_code=502,
            detail=(
                "The pass finished but produced nothing citable — every claim "
                "was dropped for missing its source quote. Any earlier dossier "
                "for this person has been kept."
            ),
        )

    faculty.dossier = markdown
    faculty.dossier_model = settings.model_for(ClaudeTask.FACULTY_DOSSIER)
    faculty.dossier_researched_at = datetime.now()
    # Only fill what the directory left blank: a line the user typed themselves
    # is theirs, and a re-research should not quietly overwrite it.
    if found.research_areas and not (faculty.research_areas or "").strip():
        faculty.research_areas = found.research_areas
    if found.homepage_url and not (faculty.homepage_url or "").strip():
        faculty.homepage_url = found.homepage_url
    session.commit()
    session.refresh(faculty)
    return faculty


@router.delete("/faculty/{faculty_id}", status_code=204)
def delete_faculty(faculty_id: int, session: Session = Depends(get_session)) -> None:
    """Remove one faculty row.

    How an over-long list gets pruned back to a shortlist. Deliberately the
    user's action and never inferred: the cap applies to what a new pass
    writes, and nothing deletes rows already on their machine.
    """
    faculty = _get_faculty(session, faculty_id)
    session.delete(faculty)
    session.commit()


@router.post(
    "/programs/{program_id}/suggest-faculty",
    response_model=SuggestFacultyOut,
)
async def suggest_faculty(
    program_id: int,
    payload: SuggestFacultyRequest,
    session: Session = Depends(get_session),
) -> SuggestFacultyOut:
    program = session.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    official_url = (payload.official_url or program.portal_url or "").strip()
    if not official_url:
        raise HTTPException(
            status_code=400,
            detail="Provide an official department URL (or set the program's portal URL).",
        )

    try:
        result = await fac_ai.suggest_faculty(program, official_url)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Suggest faculty failed: {exc}") from exc
    return SuggestFacultyOut.model_validate(result.model_dump())


# ── Notes ──────────────────────────────────────────────────────────────────
# Purely user-typed (unlike a program's notes, no Claude contract ever writes
# one of these), so there's no Rule 8 provenance to carry -- just text and a
# manual order.
@router.post("/faculty/{faculty_id}/notes", response_model=FacultyNoteOut, status_code=201)
def add_faculty_note(
    faculty_id: int,
    payload: FacultyNoteCreate,
    session: Session = Depends(get_session),
) -> FacultyNote:
    _get_faculty(session, faculty_id)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Note needs text")
    highest = session.scalar(
        select(func.max(FacultyNote.sort_order)).where(FacultyNote.faculty_id == faculty_id)
    )
    note = FacultyNote(faculty_id=faculty_id, text=text, sort_order=(highest or 0) + 1)
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


def _load_faculty_note(session: Session, faculty_id: int, note_id: int) -> FacultyNote:
    note = session.get(FacultyNote, note_id)
    if note is None or note.faculty_id != faculty_id:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.patch("/faculty/{faculty_id}/notes/{note_id}", response_model=FacultyNoteOut)
def update_faculty_note(
    faculty_id: int,
    note_id: int,
    payload: FacultyNoteUpdate,
    session: Session = Depends(get_session),
) -> FacultyNote:
    note = _load_faculty_note(session, faculty_id, note_id)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Note needs text")
    note.text = text
    session.commit()
    session.refresh(note)
    return note


@router.post(
    "/faculty/{faculty_id}/notes/reorder", response_model=list[FacultyNoteOut]
)
def reorder_faculty_notes(
    faculty_id: int,
    payload: FacultyNoteReorderRequest,
    session: Session = Depends(get_session),
) -> list[FacultyNote]:
    """Same defensive full-set check as the program-note reorder."""
    _get_faculty(session, faculty_id)
    existing = {
        n.id: n
        for n in session.scalars(
            select(FacultyNote).where(FacultyNote.faculty_id == faculty_id)
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
        select(FacultyNote)
        .where(FacultyNote.faculty_id == faculty_id)
        .order_by(FacultyNote.sort_order)
    ).all()
    return list(notes)


@router.delete("/faculty/{faculty_id}/notes/{note_id}", status_code=204)
def delete_faculty_note(
    faculty_id: int, note_id: int, session: Session = Depends(get_session)
) -> None:
    note = _load_faculty_note(session, faculty_id, note_id)
    session.delete(note)
    session.commit()
