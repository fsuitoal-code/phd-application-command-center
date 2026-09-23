"""DocType — one slot in a program's "My Docs" tab: CV, Statement of Purpose,
or a custom document the user adds.

Same built-in/custom shape as ``ProgramStep``: ``BUILTIN_DOC_TYPES`` seeds every
new program with CV and SOP, but any type — built-in or custom — can be
renamed or deleted from there on. Belongs to a program, same as ``ProgramStep``
— each program's documents are independent (a CV or SOP tailored to that
program), not shared across the list. There is no Claude involvement in this
table; it is pure file storage (``DocFile``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.doc_file import DocFile
    from app.models.program import Program


class DocType(Base):
    __tablename__ = "doc_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(60))
    #: Stored rather than derived so a custom type needs no special case.
    title: Mapped[str] = mapped_column(String(200))
    #: Distinguishes a BUILTIN_DOC_TYPES-seeded row from one the user added;
    #: both may be renamed or deleted (same rule as ProgramStep.is_custom).
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    #: Newest first — same "plain list, nothing overwritten" order the old
    #: CV uploads used.
    files: Mapped[list["DocFile"]] = relationship(
        back_populates="doc_type",
        cascade="all, delete-orphan",
        order_by="DocFile.created_at.desc()",
    )

    program: Mapped["Program"] = relationship(back_populates="doc_types")
