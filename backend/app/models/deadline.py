"""Deadlines belonging to a program. Drives main-page sort and urgency."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import DeadlineType, RequirementSource

if TYPE_CHECKING:
    from app.models.program import Program


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(40), default=DeadlineType.APPLICATION.value)
    #: Nullable: every new program is seeded with an Application deadline even
    #: when no date is known yet (manual add, or a research pass that found
    #: nothing), shown as "No deadline" until the user fills one in.
    date: Mapped[date | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    #: Position in the user's manual ordering, set by dragging rows — same
    #: pattern as ProgramStep.sort_order.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    #: Rule 8, same as Requirement: researched vs confirmed_by_program, shares
    #: the enum since the meaning is identical.
    source: Mapped[str] = mapped_column(
        String(40), default=RequirementSource.RESEARCHED.value
    )
    needs_human_verification: Mapped[bool] = mapped_column(default=True)

    program: Mapped["Program"] = relationship(back_populates="deadlines")
