"""my notes: optional link, attached file and due date

Additive only: four nullable columns on ``my_notes``. Existing notes keep their
text and gain nothing, so no data is at risk. ``downgrade()`` drops the columns
(and with them any links/dates entered since); attached files stay on disk in
``<app-data>/notes/``.

Revision ID: b91f4d7c2a58
Revises: a6c2e8d41f73
Create Date: 2026-09-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b91f4d7c2a58'
down_revision: Union[str, None] = 'a6c2e8d41f73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('my_notes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('link_url', sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column('due_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('file_name', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('file_path', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('my_notes', schema=None) as batch_op:
        batch_op.drop_column('file_path')
        batch_op.drop_column('file_name')
        batch_op.drop_column('due_date')
        batch_op.drop_column('link_url')
