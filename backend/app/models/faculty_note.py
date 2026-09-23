"""Notes belonging to one faculty member — purely user-typed.

Unlike ``ProgramNote``, no Claude contract ever writes these (a dossier is its
own separate field), so there is no Rule 8 provenance to track: no
``source``, no ``quote``, no ``needs_human_verification``. Just the user's own
words about this person.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.faculty import Faculty


class FacultyNote(Base):
    __tablename__ = "faculty_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    #: Position in the user's manual ordering, set by dragging rows -- same
    #: pattern as ProgramNote.sort_order.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    faculty: Mapped["Faculty"] = relationship(back_populates="notes")
