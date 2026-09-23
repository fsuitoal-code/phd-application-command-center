"""Drop the "current CV" flag — uploads are a plain list

``cv_uploads.is_active`` encoded a rule the user did not want: exactly one CV
"current", the rest "superseded", with activation to keep in sync. Uploads are
now a flat list, newest first, and a review simply reads the most recent one.

No data is lost that the user would miss: every upload is kept, only the flag
distinguishing them goes.

Revision ID: d51b8ac3e7f2
Revises: c4e1f07b52aa
Create Date: 2026-09-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd51b8ac3e7f2'
down_revision: Union[str, None] = 'c4e1f07b52aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite needs the table rebuilt to drop a column.
    with op.batch_alter_table('cv_uploads', schema=None) as batch_op:
        batch_op.drop_column('is_active')


def downgrade() -> None:
    with op.batch_alter_table('cv_uploads', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    # Restore the old invariant as best we can: the newest upload is the active one.
    op.execute(
        "UPDATE cv_uploads SET is_active = 1 WHERE id = (SELECT id FROM cv_uploads "
        "ORDER BY created_at DESC, id DESC LIMIT 1)"
    )
