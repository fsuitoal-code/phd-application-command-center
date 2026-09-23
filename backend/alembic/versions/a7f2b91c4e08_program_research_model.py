"""record which model researched a program

Revision ID: a7f2b91c4e08
Revises: d51b8ac3e7f2
Create Date: 2026-09-20

Programs carry `source = researched` on every fact but never recorded WHICH
model produced them, so a question as basic as "was this pass Sonnet or Opus?"
could not be answered from the data — only guessed at from the config as it
stands today, which changes.

Nullable on purpose: rows that predate this column genuinely do not know, and
NULL says that honestly. A backfill would have to invent an answer.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f2b91c4e08'
down_revision: Union[str, None] = 'd51b8ac3e7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('research_model', sa.String(length=100), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.drop_column('research_model')
