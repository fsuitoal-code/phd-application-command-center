"""faculty manual sort order

Revision ID: 2b7e5f9a1c34
Revises: f151b2832c56
Create Date: 2026-09-21

Adds sort_order to faculty so a program's shortlist can be dragged into any
order, same pattern as deadlines.sort_order / program_steps.sort_order.
Seeds it from each program's current alphabetical order (then id) so the
first drag doesn't scramble a list that used to be shown by name.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b7e5f9a1c34'
down_revision: Union[str, None] = 'f151b2832c56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('faculty', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0')
        )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, program_id FROM faculty ORDER BY program_id, name, id")
    ).fetchall()
    counters: dict[int, int] = {}
    for row in rows:
        index = counters.get(row.program_id, 0)
        bind.execute(
            sa.text("UPDATE faculty SET sort_order = :o WHERE id = :id"),
            {"o": index, "id": row.id},
        )
        counters[row.program_id] = index + 1

    with op.batch_alter_table('faculty', schema=None) as batch_op:
        batch_op.alter_column('sort_order', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('faculty', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
