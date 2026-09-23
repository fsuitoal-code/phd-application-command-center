"""program manual sort order

Revision ID: 9b3f2c8ad514
Revises: 7c1a9e4b2d30
Create Date: 2026-09-19

Adds the column behind GET /programs?sort=manual, and seeds it from the order
the user is already looking at rather than leaving every row at 0 — so the
first switch to "My order" doesn't scramble the list.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b3f2c8ad514'
down_revision: Union[str, None] = '7c1a9e4b2d30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0')
        )

    # Seed the manual order from each program's EARLIEST deadline, then id.
    # Deliberately not "next upcoming deadline": that would make the backfill
    # depend on the date the migration happens to run.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT p.id, MIN(d.date) AS first_deadline
            FROM programs p
            LEFT JOIN deadlines d ON d.program_id = p.id
            GROUP BY p.id
            ORDER BY (first_deadline IS NULL), first_deadline, p.id
            """
        )
    ).fetchall()
    for index, row in enumerate(rows):
        bind.execute(
            sa.text("UPDATE programs SET sort_order = :o WHERE id = :id"),
            {"o": index, "id": row[0]},
        )

    # Drop the server_default now the column is populated: the ORM supplies the
    # value from here on, matching how every other column in this schema works.
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.alter_column('sort_order', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
