"""Faculty belonging to a program."""

from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.faculty_note import FacultyNote
    from app.models.program import Program


class Faculty(Base):
    __tablename__ = "faculty"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    research_areas: Mapped[str | None] = mapped_column(Text, default=None)
    homepage_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    contacted: Mapped[bool] = mapped_column(default=False)
    #: Position in the user's manual ordering, set by dragging cards -- same
    #: pattern as Deadline.sort_order / ProgramStep.sort_order.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    #: The researched profile of this person: markdown sections, each claim a
    #: bullet citing the sentence it came from. Assembled by
    #: ``app.claude.faculty_dossier`` and rendered by the same component that
    #: renders a program's notes.
    dossier: Mapped[str | None] = mapped_column(Text, default=None)
    #: Provenance (Rule 8): which model produced the dossier above, which is
    #: not the same question as what a pass would use today.
    dossier_model: Mapped[str | None] = mapped_column(String(100), default=None)
    dossier_researched_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=None
    )

    program: Mapped["Program"] = relationship(back_populates="faculty")
    notes: Mapped[list["FacultyNote"]] = relationship(
        back_populates="faculty",
        cascade="all, delete-orphan",
        order_by="FacultyNote.sort_order",
    )
