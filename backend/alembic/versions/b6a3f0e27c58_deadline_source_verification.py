"""deadline source and needs_human_verification

Revision ID: b6a3f0e27c58
Revises: d8e4a1c6f930
Create Date: 2026-09-21

Adds Rule 8 provenance to deadlines, same as requirements: source
(researched | confirmed_by_program) + needs_human_verification, so the
verify/confirm badge can distinguish a Claude-found date from a hand-typed
or placeholder one. Existing rows backfill to confirmed/no-verification --
deliberate, so old data the user has already been looking at doesn't
suddenly grow a "please verify" badge.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6a3f0e27c58'
down_revision: Union[str, None] = 'd8e4a1c6f930'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('deadlines', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'source', sa.String(length=40), nullable=False,
                server_default='confirmed_by_program',
            )
        )
        batch_op.add_column(
            sa.Column(
                'needs_human_verification', sa.Boolean(), nullable=False,
                server_default=sa.false(),
            )
        )

    with op.batch_alter_table('deadlines', schema=None) as batch_op:
        batch_op.alter_column('source', server_default=None)
        batch_op.alter_column('needs_human_verification', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('deadlines', schema=None) as batch_op:
        batch_op.drop_column('needs_human_verification')
        batch_op.drop_column('source')
