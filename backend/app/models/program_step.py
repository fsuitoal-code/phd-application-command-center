"""ProgramStep — one step of an application, per program.

The seven built-in steps (``BUILTIN_STEPS``) are materialised for every program;
a program may also carry custom steps of its own. Completion is *always* set by
the user: the app never infers that a step is done from the presence of other
data, so "gathered but still incomplete" stays expressible.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.program import Program


class ProgramStep(Base):
    __tablename__ = "program_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(60))
    #: Stored rather than derived so a custom step needs no special case.
    label: Mapped[str] = mapped_column(String(200))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    #: Distinguishes a ``BUILTIN_STEPS``-seeded step from one the user added;
    #: both may be renamed or deleted per program from here on.
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)

    program: Mapped["Program"] = relationship(back_populates="steps")
