"""DocFile — one uploaded file under a doc type.

Uploads are a plain list, newest first, with no "current" flag — same pattern
today's CV uploads used before My Docs generalized it to N doc types. Nothing
is overwritten by a new upload; the user deletes what they no longer want.

There is no extracted ``text`` here (unlike the old CvUpload): nothing reads a
doc's content any more — CV review and faculty fit, the only two features that
ever read it, have both been removed. This is pure file storage, served back
generically via ``mimetypes.guess_type`` rather than a fixed format column.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import utcnow

if TYPE_CHECKING:
    from app.models.doc_type import DocType


class DocFile(Base):
    __tablename__ = "doc_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type_id: Mapped[int] = mapped_column(
        ForeignKey("doc_types.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(500))
    #: Nullable only for the instant between the row's flush (to get its id
    #: for the stored filename) and the update that sets this — never null
    #: once the request completes.
    stored_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    doc_type: Mapped["DocType"] = relationship(back_populates="files")
