"""deadline date nullable

Revision ID: a2c7e5f19b3d
Revises: f1a4c9e0b6d2
Create Date: 2026-09-21

Every new program is now seeded with an Application deadline, even when no
date is known (manual add, or a research pass that found nothing). That
placeholder has to be storable without a date, shown as "No deadline" until
the user fills one in — so deadlines.date drops its NOT NULL constraint.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c7e5f19b3d'
down_revision: Union[str, None] = 'f1a4c9e0b6d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('deadlines', schema=None) as batch_op:
        batch_op.alter_column('date', existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    # A downgrade with any NULL dates present would violate the restored NOT
    # NULL constraint; nothing here needs a backfill value invented for it.
    with op.batch_alter_table('deadlines', schema=None) as batch_op:
        batch_op.alter_column('date', existing_type=sa.Date(), nullable=False)
