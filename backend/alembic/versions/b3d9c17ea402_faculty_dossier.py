"""give each faculty member a researched dossier

Revision ID: b3d9c17ea402
Revises: a7f2b91c4e08
Create Date: 2026-09-20

A faculty row held a name, a line of research areas and a fit summary — enough
to list someone, nowhere near enough to decide whether to spend an application
on them. `dossier` holds the researched profile of one person: markdown
sections whose every claim cites the sentence it came from, assembled by
`app.claude.faculty_dossier` and rendered by the same component as a program's
notes.

`dossier_model` and `dossier_researched_at` are provenance (Rule 8). A pass is
billed and cap-counted, so "when was this written, and by which model" is a
question the user will actually ask before trusting it or paying to redo it.

All three nullable and additive: every existing row genuinely has no dossier,
and NULL says so. Nothing is rewritten, so this is safe on a populated DB.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d9c17ea402'
down_revision: Union[str, None] = 'a7f2b91c4e08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('faculty', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dossier', sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column('dossier_model', sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column('dossier_researched_at', sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('faculty', schema=None) as batch_op:
        batch_op.drop_column('dossier_researched_at')
        batch_op.drop_column('dossier_model')
        batch_op.drop_column('dossier')
