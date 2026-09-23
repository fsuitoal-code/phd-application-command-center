"""My Notes: a program's free-form notes, each with optional link, file and date.

Pure user data — no Claude involvement. Attached files are stored next to the
database (Rule 2), same as My Docs uploads, and served back inline.
"""

from __future__ import annotations

import mimetypes
import re
from datetime import date
from pathlib import Path, PurePath
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import MyNote, Program
from app.paths import notes_dir
from app.schemas import MyNoteOut, MyNoteReorderRequest, MyNoteUpdate

router = APIRouter(prefix="/api/programs", tags=["my-notes"])

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_EMPTY = "A note needs text, a link, a file or a date"


def _require_program(session: Session, program_id: int) -> None:
    if session.get(Program, program_id) is None:
        raise HTTPException(status_code=404, detail="Program not found")


def _load(session: Session, program_id: int, note_id: int) -> MyNote:
    note = session.get(MyNote, note_id)
    if note is None or note.program_id != program_id:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


def _clean_link(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Link must be an http(s) URL")
    return value


def _parse_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD") from None


def _drop_file(note: MyNote) -> None:
    if note.file_path:
        Path(note.file_path).unlink(missing_ok=True)
    note.file_name = None
    note.file_path = None


async def _attach(note: MyNote, upload: UploadFile) -> None:
    """Store the upload for an already-flushed note, replacing any previous file."""
    data = await upload.read()
    name = PurePath(upload.filename or "file").name
    _drop_file(note)
    safe = _UNSAFE.sub("_", name) or "file"
    # SQLite reuses the highest id once it is deleted, so the id alone could
    # land on a file a previous note left behind.
    dest = notes_dir() / f"{note.id}-{uuid4().hex[:8]}-{safe}"
    dest.write_bytes(data)
    note.file_name = name
    note.file_path = str(dest)


@router.post("/{program_id}/my-notes", response_model=MyNoteOut, status_code=201)
async def add_my_note(
    program_id: int,
    text: str = Form(""),
    link_url: str | None = Form(None),
    due_date: str | None = Form(None),
    file: UploadFile | None = File(None),
    session: Session = Depends(get_session),
) -> MyNote:
    _require_program(session, program_id)
    if file is not None and not file.filename:
        file = None
    note = MyNote(
        program_id=program_id,
        text=text.strip(),
        link_url=_clean_link(link_url),
        due_date=_parse_date(due_date),
    )
    if note.is_empty() and file is None:
        raise HTTPException(status_code=400, detail=_EMPTY)
    highest = session.scalar(
        select(func.max(MyNote.sort_order)).where(MyNote.program_id == program_id)
    )
    note.sort_order = (highest or 0) + 1
    session.add(note)
    session.flush()  # need the id for the stored filename
    if file is not None:
        await _attach(note, file)
    session.commit()
    session.refresh(note)
    return note


@router.patch("/{program_id}/my-notes/{note_id}", response_model=MyNoteOut)
def set_my_note(
    program_id: int,
    note_id: int,
    payload: MyNoteUpdate,
    session: Session = Depends(get_session),
) -> MyNote:
    note = _load(session, program_id, note_id)
    fields = payload.model_dump(exclude_unset=True)
    if "text" in fields:
        note.text = (fields["text"] or "").strip()
    if "link_url" in fields:
        note.link_url = _clean_link(fields["link_url"])
    if "due_date" in fields:
        note.due_date = fields["due_date"]
    if note.is_empty():
        raise HTTPException(status_code=400, detail=_EMPTY)
    session.commit()
    session.refresh(note)
    return note


@router.put("/{program_id}/my-notes/{note_id}/file", response_model=MyNoteOut)
async def replace_my_note_file(
    program_id: int,
    note_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> MyNote:
    note = _load(session, program_id, note_id)
    await _attach(note, file)
    session.commit()
    session.refresh(note)
    return note


@router.delete("/{program_id}/my-notes/{note_id}/file", response_model=MyNoteOut)
def remove_my_note_file(
    program_id: int, note_id: int, session: Session = Depends(get_session)
) -> MyNote:
    note = _load(session, program_id, note_id)
    if not (note.text or note.link_url or note.due_date):
        raise HTTPException(
            status_code=400, detail="The file is all this note holds; delete the note instead"
        )
    _drop_file(note)
    session.commit()
    session.refresh(note)
    return note


@router.get("/{program_id}/my-notes/{note_id}/file")
def open_my_note_file(
    program_id: int, note_id: int, session: Session = Depends(get_session)
) -> FileResponse:
    note = _load(session, program_id, note_id)
    if not note.file_path:
        raise HTTPException(status_code=404, detail="This note has no file")
    path = Path(note.file_path)
    # A hand-edited database must not be able to serve arbitrary files.
    try:
        path.resolve().relative_to(notes_dir().resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="File is not readable.") from None
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="The attached file is missing from this machine — attach it again.",
        )
    media_type, _ = mimetypes.guess_type(note.file_name or "")
    return FileResponse(
        path,
        media_type=media_type or "application/octet-stream",
        filename=note.file_name,
        content_disposition_type="inline",
    )


@router.post("/{program_id}/my-notes/reorder", response_model=list[MyNoteOut])
def reorder_my_notes(
    program_id: int,
    payload: MyNoteReorderRequest,
    session: Session = Depends(get_session),
) -> list[MyNote]:
    """Same defensive full-set check as the other reorders."""
    _require_program(session, program_id)
    existing = {
        n.id: n
        for n in session.scalars(select(MyNote).where(MyNote.program_id == program_id)).all()
    }
    if sorted(payload.ids) != sorted(existing):
        raise HTTPException(
            status_code=400,
            detail="Reorder must list every note exactly once; reload and retry",
        )
    for index, nid in enumerate(payload.ids):
        existing[nid].sort_order = index
    session.commit()
    return list(
        session.scalars(
            select(MyNote).where(MyNote.program_id == program_id).order_by(MyNote.sort_order)
        ).all()
    )


@router.delete("/{program_id}/my-notes/{note_id}", status_code=204)
def delete_my_note(
    program_id: int, note_id: int, session: Session = Depends(get_session)
) -> None:
    note = _load(session, program_id, note_id)
    _drop_file(note)
    session.delete(note)
    session.commit()
