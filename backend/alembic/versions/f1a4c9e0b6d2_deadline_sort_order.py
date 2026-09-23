"""deadline manual sort order

Revision ID: f1a4c9e0b6d2
Revises: 9a14f8506800
Create Date: 2026-09-21

Adds sort_order to deadlines so a program's list can be dragged into any
order, same pattern as program_steps.sort_order and programs.sort_order.
Seeds it from each deadline's current date order (then id) so the first
drag doesn't scramble a list that used to be shown sorted by date.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a4c9e0b6d2'
down_revision: Union[str, None] = '9a14f8506800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('deadlines', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0')
        )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, program_id FROM deadlines ORDER BY program_id, date, id"
        )
    ).fetchall()
    counters: dict[int, int] = {}
    for row in rows:
        index = counters.get(row.program_id, 0)
        bind.execute(
            sa.text("UPDATE deadlines SET sort_order = :o WHERE id = :id"),
            {"o": index, "id": row.id},
        )
        counters[row.program_id] = index + 1

    with op.batch_alter_table('deadlines', schema=None) as batch_op:
        batch_op.alter_column('sort_order', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('deadlines', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
