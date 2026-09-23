"""The user's own notes about one program — the "My Notes" tab.

A free-form scratchpad: text plus, optionally, one link, one attached file and
one due date. Purely user-typed, like ``FacultyNote``, so there is no Rule 8
provenance to track — unlike ``ProgramNote``, which holds cited facts from a
research pass. A note must carry at least one of the four.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import utcnow

if TYPE_CHECKING:
    from app.models.program import Program


class MyNote(Base):
    __tablename__ = "my_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text, default="")
    link_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    #: A reminder date on the note itself — not a row in ``deadlines``, so it
    #: does not drive the program's urgency.
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    #: Original name of the attached file; the bytes live in ``paths.notes_dir()``.
    file_name: Mapped[str | None] = mapped_column(String(500), default=None)
    file_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    #: Counts as program activity for staleness (see ``insights``).
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    program: Mapped["Program"] = relationship(back_populates="my_notes")

    def is_empty(self) -> bool:
        return not (self.text or self.link_url or self.due_date or self.file_name)
