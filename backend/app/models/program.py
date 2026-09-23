"""The Program entity — a target PhD/MS program. The main-page unit."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import utcnow

if TYPE_CHECKING:
    from app.models.deadline import Deadline
    from app.models.doc_type import DocType
    from app.models.faculty import Faculty
    from app.models.my_note import MyNote
    from app.models.program_note import ProgramNote
    from app.models.program_step import ProgramStep
    from app.models.requirement import Requirement


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    university: Mapped[str] = mapped_column(String(300))
    department: Mapped[str | None] = mapped_column(String(300), default=None)
    degree: Mapped[str | None] = mapped_column(String(50), default=None)  # PhD / MS
    #: The program's or department's own page. Doubles as the seed domain the
    #: Rule 3 research pass is locked to -- NOT where an application is filed.
    portal_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    #: The graduate application portal: where the user actually submits. Kept
    #: separate because it is usually the university's central system, on a
    #: different host from the department page above.
    application_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    #: The program's point of contact for admissions questions.
    admissions_email: Mapped[str | None] = mapped_column(String(320), default=None)
    #: Claude model that produced the researched facts, recorded at the time
    #: of the pass. NULL for a program added by hand, or researched before
    #: this was tracked -- the config only says what a pass would use TODAY.
    research_model: Mapped[str | None] = mapped_column(String(100), default=None)
    #: Position in the user's manual ordering, set by dragging rows.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    date_added: Mapped[datetime] = mapped_column(default=utcnow)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    faculty: Mapped[list["Faculty"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="Faculty.sort_order",
    )
    deadlines: Mapped[list["Deadline"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="Deadline.sort_order",
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="Requirement.sort_order",
    )
    notes: Mapped[list["ProgramNote"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="ProgramNote.sort_order",
    )
    steps: Mapped[list["ProgramStep"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="ProgramStep.sort_order",
    )
    my_notes: Mapped[list["MyNote"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="MyNote.sort_order",
    )
    doc_types: Mapped[list["DocType"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="DocType.sort_order",
    )
