"""My Docs: a program's CV, Statement of Purpose, and any custom document type.

Pure file storage — no Claude involvement. The two features that used to read
a CV's content (per-program CV review, faculty fit assessment) have both been
removed, so a doc type here is just a title and a list of uploaded files the
user can open. Belongs to a program (same as ``program_steps``): each
program's documents are independent, not shared across the list — a CV or SOP
tailored to one program never shows up on another's tab. Renaming keeps the
same behavior program_steps already has: any type, built-in or custom, may be
renamed or deleted.
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path, PurePath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import DocFile, DocType, Program
from app.models.enums import BUILTIN_DOC_TYPES
from app.paths import docs_dir
from app.schemas import DocFileOut, DocTypeCreate, DocTypeOut, DocTypeUpdate

router = APIRouter(prefix="/api/docs", tags=["docs"])
program_router = APIRouter(prefix="/api/programs", tags=["docs"])

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def ensure_doc_types(session: Session, program_id: int) -> None:
    """Materialise the built-in doc types (CV, SOP) for a program.

    No-op once the program already has any DocType row — same lazy-seed
    pattern as ``programs.ensure_steps``, so it is safe to call on every
    My Docs load.
    """
    existing = session.scalar(
        select(func.count()).select_from(DocType).where(DocType.program_id == program_id)
    )
    if existing:
        return
    for order, (key, title) in enumerate(BUILTIN_DOC_TYPES):
        session.add(DocType(program_id=program_id, key=key, title=title, sort_order=order))
    session.commit()


def _doc_types(session: Session, program_id: int) -> list[DocType]:
    return list(
        session.scalars(
            select(DocType)
            .where(DocType.program_id == program_id)
            .options(selectinload(DocType.files))
            .order_by(DocType.sort_order, DocType.id)
        ).all()
    )


def _store_file(file_id: int, filename: str, data: bytes) -> Path:
    """Save the upload next to the database, outside the repo (Rule 2)."""
    safe = _UNSAFE.sub("_", PurePath(filename).name) or "file"
    dest = docs_dir() / f"{file_id}-{safe}"
    dest.write_bytes(data)
    return dest


# ── Program-scoped: list, add a type, upload a file ────────────────────────
@program_router.get("/{program_id}/docs", response_model=list[DocTypeOut])
def list_docs(program_id: int, session: Session = Depends(get_session)) -> list[DocType]:
    if session.get(Program, program_id) is None:
        raise HTTPException(status_code=404, detail="Program not found")
    ensure_doc_types(session, program_id)
    return _doc_types(session, program_id)


@program_router.post("/{program_id}/docs", response_model=DocTypeOut, status_code=201)
def add_doc_type(
    program_id: int, payload: DocTypeCreate, session: Session = Depends(get_session)
) -> DocType:
    if session.get(Program, program_id) is None:
        raise HTTPException(status_code=404, detail="Program not found")
    ensure_doc_types(session, program_id)
    next_order = (
        session.scalar(
            select(func.count()).select_from(DocType).where(DocType.program_id == program_id)
        )
        or 0
    )
    key = _UNSAFE.sub("_", payload.title.strip().lower()) or "doc"
    row = DocType(
        program_id=program_id,
        key=key,
        title=payload.title.strip(),
        is_custom=True,
        sort_order=next_order,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@program_router.post(
    "/{program_id}/docs/{doc_type_id}/files", response_model=DocFileOut, status_code=201
)
async def upload_file(
    program_id: int,
    doc_type_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> DocFile:
    doc_type = session.get(DocType, doc_type_id)
    if doc_type is None or doc_type.program_id != program_id:
        raise HTTPException(status_code=404, detail="Doc type not found")
    data = await file.read()
    row = DocFile(doc_type_id=doc_type_id, filename=PurePath(file.filename or "file").name)
    session.add(row)
    session.flush()  # need the id for the stored filename
    row.stored_path = str(_store_file(row.id, file.filename or "file", data))
    session.commit()
    session.refresh(row)
    return row


# ── Flat: a doc type or file id alone is enough ─────────────────────────────
@router.patch("/{doc_type_id}", response_model=DocTypeOut)
def rename_doc_type(
    doc_type_id: int, payload: DocTypeUpdate, session: Session = Depends(get_session)
) -> DocType:
    row = session.get(DocType, doc_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Doc type not found")
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be blank")
    row.title = title
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{doc_type_id}", status_code=204)
def delete_doc_type(doc_type_id: int, session: Session = Depends(get_session)) -> None:
    row = session.get(DocType, doc_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Doc type not found")
    for f in row.files:
        Path(f.stored_path).unlink(missing_ok=True)
    session.delete(row)
    session.commit()


@router.get("/files/{file_id}")
def open_file(file_id: int, session: Session = Depends(get_session)) -> FileResponse:
    row = session.get(DocFile, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")

    path = Path(row.stored_path)
    # The path comes from our own row, but resolve it against the docs
    # directory anyway: a hand-edited database must not serve arbitrary files.
    try:
        path.resolve().relative_to(docs_dir().resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="File is not readable.") from None
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="The uploaded file is missing from this machine — re-upload it.",
        )

    media_type, _ = mimetypes.guess_type(row.filename)
    return FileResponse(
        path,
        media_type=media_type or "application/octet-stream",
        filename=row.filename,
        content_disposition_type="inline",
    )


@router.delete("/files/{file_id}", status_code=204)
def delete_file(file_id: int, session: Session = Depends(get_session)) -> None:
    row = session.get(DocFile, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    Path(row.stored_path).unlink(missing_ok=True)
    session.delete(row)
    session.commit()
