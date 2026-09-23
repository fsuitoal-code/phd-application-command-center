"""Notes belonging to a program — individually cited, confirmable facts.

Replaces the old single markdown-blob ``programs.notes`` column (dropped in
``e4b1a9c2d6f7``, archived first per Rule 10). Rule 8: each carries a
``source`` (researched vs confirmed_by_program) and a ``needs_human_verification``
flag, same pattern as ``Requirement`` and ``Deadline``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import RequirementSource

if TYPE_CHECKING:
    from app.models.program import Program


class ProgramNote(Base):
    __tablename__ = "program_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    #: The one-sentence, applicant-facing summary of the fact.
    text: Mapped[str] = mapped_column(Text)
    #: The exact source sentence backing "text". Null for a hand-added note
    #: or legacy uncited prose, which is also what excludes it from the
    #: verify badge (nothing to verify without a quote to check against).
    quote: Mapped[str | None] = mapped_column(Text, default=None)
    #: Already the fragment-decorated URL (quote_fragment_url) exactly as
    #: rendered -- the frontend just links to it, no markdown parsing needed.
    source_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    source_label: Mapped[str | None] = mapped_column(String(200), default=None)
    source: Mapped[str] = mapped_column(
        String(40), default=RequirementSource.RESEARCHED.value
    )
    needs_human_verification: Mapped[bool] = mapped_column(default=True)
    #: Position in the user's manual ordering, set by dragging rows — same
    #: pattern as Deadline.sort_order.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    program: Mapped["Program"] = relationship(back_populates="notes")
