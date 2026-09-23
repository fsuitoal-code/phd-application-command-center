"""drop the applicant profile

The applicant profile (research interests, keywords, background...) lost its
editor when the Dossier page was removed, and nothing reads it any more: the
research passes rank faculty by the department's own emphasis instead.

DATA LOSS WARNING (Rule 10): before dropping, if any row holds something the
user typed, every row is exported to
``<app-data>/archive/applicant-profile-<UTC stamp>.json``, same pattern as
``d4f8a1c62b9e_drop_outreach_and_documents.py``. A row with nothing but its
id and timestamps -- the only kind the app could create once the editor was
gone -- is not worth a file.

``downgrade()`` restores the schema only (an empty table) -- the archived JSON
is the way to get the data back, not this migration.

Revision ID: 37185aa3f20d
Revises: b91f4d7c2a58
Create Date: 2026-09-22
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '37185aa3f20d'
down_revision: Union[str, None] = 'b91f4d7c2a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Columns that only record a row's identity and timing, not anything typed.
_BOOKKEEPING = {"id", "created_at", "updated_at"}


def _jsonable(value):
    if hasattr(value, "isoformat"):  # datetime or date
        return value.isoformat()
    return value


def _archive_profile(bind) -> None:
    """Export the profile rows before dropping them, if any holds real content."""
    from app.paths import archive_dir

    if "applicant_profile" not in sa.inspect(bind).get_table_names():
        return
    rows = bind.execute(sa.text("SELECT * FROM applicant_profile")).mappings().all()
    typed = any(
        key not in _BOOKKEEPING and value is not None and str(value).strip()
        for row in rows
        for key, value in row.items()
    )
    if not typed:
        return  # nothing the user typed (fresh install, or an untouched row)

    payload = {
        "applicant_profile": [{k: _jsonable(v) for k, v in row.items()} for row in rows]
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = archive_dir() / f"applicant-profile-{stamp}.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived applicant_profile rows to {dest}")


def upgrade() -> None:
    _archive_profile(op.get_bind())
    op.drop_table('applicant_profile')


def downgrade() -> None:
    op.create_table(
        'applicant_profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target_degree', sa.String(length=100), nullable=True),
        sa.Column('research_interests', sa.Text(), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('background_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('funding_needs', sa.Text(), nullable=True),
        sa.Column('test_status', sa.Text(), nullable=True),
        sa.Column('cv_emphasis_rules', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
