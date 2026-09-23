"""record where a program is actually applied to

Revision ID: e2c5d80a1f64
Revises: b3d9c17ea402
Create Date: 2026-09-20

`portal_url` was carrying two jobs: the department/program page (which is also
the seed domain the Rule 3 research pass is locked to) and, by its name, the
place you submit an application. Those are almost never the same host -- the
department runs its own site, the application goes through the graduate
school's central system -- so the apply link had nowhere to live.

Nullable on purpose, with no backfill: nothing in an existing row says where
that program's application portal is, and guessing one from the department
domain would write a researched-looking fact nobody researched.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2c5d80a1f64'
down_revision: Union[str, None] = 'b3d9c17ea402'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('application_url', sa.String(length=1000), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.drop_column('application_url')
