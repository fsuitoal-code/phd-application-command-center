"""faculty notes table

A small table of purely user-typed notes about one faculty member, dragged
into order the same way as ``program_notes`` -- but unlike ``program_notes``,
no Claude contract ever writes these (a dossier is its own separate field),
so there's no Rule 8 provenance to carry: no ``quote`` / ``source_url`` /
``source_label`` / ``source`` / ``needs_human_verification``, just ``text``
and ``sort_order``.

Revision ID: f3a7c1e9b204
Revises: d4f8a1c62b9e
Create Date: 2026-09-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a7c1e9b204'
down_revision: Union[str, None] = 'd4f8a1c62b9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'faculty_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('faculty_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['faculty_id'], ['faculty.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('faculty_notes', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_faculty_notes_faculty_id'), ['faculty_id'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('faculty_notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_faculty_notes_faculty_id'))
    op.drop_table('faculty_notes')
