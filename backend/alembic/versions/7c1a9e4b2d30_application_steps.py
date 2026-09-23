"""application steps checklist

Revision ID: 7c1a9e4b2d30
Revises: 0de4dd527cd1
Create Date: 2026-09-19

Adds the per-program application checklist and backfills the eight built-in
steps for every program that already exists, so an upgrade leaves populated
databases with a full checklist rather than an empty one.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1a9e4b2d30'
down_revision: Union[str, None] = '0de4dd527cd1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Kept literal rather than imported from app.models.enums: a migration must
# describe the schema at this revision, not follow later edits to the enum.
BUILTIN_STEPS = [
    ("researched", "Researched"),
    ("requirements", "Requirements"),
    ("deadlines", "Deadlines"),
    ("faculty", "Faculty"),
    ("sop", "SOP"),
    ("cv", "CV"),
    ("recommenders", "Recommenders"),
    ("submitted", "Submitted"),
]


def upgrade() -> None:
    op.create_table(
        'program_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=60), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_custom', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('program_steps', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_program_steps_program_id'), ['program_id'], unique=False
        )

    # Backfill: give every existing program the full checklist, all unticked.
    bind = op.get_bind()
    program_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM programs"))]
    if program_ids:
        steps = sa.table(
            'program_steps',
            sa.column('program_id', sa.Integer),
            sa.column('key', sa.String),
            sa.column('label', sa.String),
            sa.column('completed', sa.Boolean),
            sa.column('completed_at', sa.DateTime),
            sa.column('sort_order', sa.Integer),
            sa.column('is_custom', sa.Boolean),
        )
        op.bulk_insert(
            steps,
            [
                {
                    'program_id': pid,
                    'key': key,
                    'label': label,
                    'completed': False,
                    'completed_at': None,
                    'sort_order': order,
                    'is_custom': False,
                }
                for pid in program_ids
                for order, (key, label) in enumerate(BUILTIN_STEPS)
            ],
        )


def downgrade() -> None:
    with op.batch_alter_table('program_steps', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_program_steps_program_id'))
    op.drop_table('program_steps')
