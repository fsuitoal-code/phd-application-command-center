"""The applicant's research identity — grounding for faculty research.

Usually one per machine. We keep an integer PK so a future multi-track
applicant is not precluded, but the app treats a single active row
(get-or-create).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import utcnow


class ApplicantProfile(Base):
    __tablename__ = "applicant_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_degree: Mapped[str | None] = mapped_column(String(100), default=None)
    research_interests: Mapped[str | None] = mapped_column(Text, default=None)
    keywords: Mapped[str | None] = mapped_column(Text, default=None)
    background_summary: Mapped[str | None] = mapped_column(Text, default=None)
    # Optional context fields.
    funding_needs: Mapped[str | None] = mapped_column(Text, default=None)
    test_status: Mapped[str | None] = mapped_column(Text, default=None)
    cv_emphasis_rules: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
