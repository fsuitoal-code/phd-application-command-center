"""requirement manual sort order

Revision ID: d8e4a1c6f930
Revises: a2c7e5f19b3d
Create Date: 2026-09-21

Adds sort_order to requirements so a program's list can be dragged into any
order, edited, and deleted like deadlines, same pattern as
deadlines.sort_order (f1a4c9e0b6d2). There is no natural existing ordering
for requirements (no date), so it is seeded from insertion order (id) per
program.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e4a1c6f930'
down_revision: Union[str, None] = 'a2c7e5f19b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('requirements', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0')
        )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, program_id FROM requirements ORDER BY program_id, id"
        )
    ).fetchall()
    counters: dict[int, int] = {}
    for row in rows:
        index = counters.get(row.program_id, 0)
        bind.execute(
            sa.text("UPDATE requirements SET sort_order = :o WHERE id = :id"),
            {"o": index, "id": row.id},
        )
        counters[row.program_id] = index + 1

    with op.batch_alter_table('requirements', schema=None) as batch_op:
        batch_op.alter_column('sort_order', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('requirements', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
