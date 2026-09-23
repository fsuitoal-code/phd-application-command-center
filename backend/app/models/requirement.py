"""Requirements belonging to a program (GRE/TOEFL/fees/waivers).

Rule 8: each carries a ``source`` (researched vs confirmed_by_program) and a
``needs_human_verification`` flag; the UI distinguishes guesses from confirmed
facts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import RequirementKind, RequirementSource

if TYPE_CHECKING:
    from app.models.program import Program


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default=RequirementKind.OTHER.value)
    value: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str] = mapped_column(
        String(40), default=RequirementSource.RESEARCHED.value
    )
    needs_human_verification: Mapped[bool] = mapped_column(default=True)
    #: Position in the user's manual ordering, set by dragging rows — same
    #: pattern as Deadline.sort_order.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    program: Mapped["Program"] = relationship(back_populates="requirements")
