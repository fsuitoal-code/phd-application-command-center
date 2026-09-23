"""program admissions email (point of contact)

Revision ID: f151b2832c56
Revises: 1c6d9a2e4f81
Create Date: 2026-09-21

The program view needs a point of contact alongside the application portal
link, and there was nowhere to put one. Nullable, no backfill -- same
reasoning as `application_url` in e2c5d80a1f64: nothing in an existing row
says what a program's admissions address is, and guessing one would write a
researched-looking fact nobody researched.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f151b2832c56'
down_revision: Union[str, None] = '1c6d9a2e4f81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('admissions_email', sa.String(length=320), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.drop_column('admissions_email')
