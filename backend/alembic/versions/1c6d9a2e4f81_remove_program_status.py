"""remove program status and stage_history, in favour of step-based progress

The Programs list row now shows a progress bar driven by ``program_steps``
completion instead of a status badge, and ``StatusSelect``/``advance_status``
were already dead code (nothing in the app called them). This DROPS
``stage_history`` entirely and the ``status`` column on ``programs``.

DATA LOSS WARNING (Rule 10): before dropping, every ``stage_history`` row and
each program's current ``status`` value is exported to
``<app-data>/archive/program-status-<UTC stamp>.json``, same pattern as
``c4e1f07b52aa_cv_upload_replaces_experience.py``.

This also backfills ``program_steps`` for any program that has none yet (one
created before the steps table existed, whose detail page was never opened —
``ensure_steps()`` only seeds lazily on a detail fetch), so every row can show
an accurate progress bar right away.

``downgrade()`` restores the schema only (``stage_history`` empty,
``programs.status`` defaulted to ``"researching"``) — the archived JSON is the
way to get the data back, not this migration.

Revision ID: 1c6d9a2e4f81
Revises: e4b1a9c2d6f7
Create Date: 2026-09-21
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '1c6d9a2e4f81'
down_revision: Union[str, None] = 'e4b1a9c2d6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Kept literal rather than imported from app.models.enums: a migration must
# describe the schema at this revision, not follow later edits to the enum.
BUILTIN_STEPS = [
    ("requirements", "Researched requirements"),
    ("deadlines", "Researched deadlines"),
    ("faculty", "Researched faculty"),
    ("faculty_outreach", "Reach out to faculty"),
    ("sop", "Essays"),
    ("cv", "Polish CV"),
    ("submitted", "Submit application"),
]


def _jsonable(value):
    if hasattr(value, "isoformat"):  # datetime or date
        return value.isoformat()
    return value


def _archive_status_data(bind) -> None:
    """Export stage_history rows and each program's status before dropping."""
    from app.paths import archive_dir

    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())

    payload: dict[str, list[dict]] = {}
    if "stage_history" in present:
        rows = bind.execute(sa.text("SELECT * FROM stage_history")).mappings().all()
        payload["stage_history"] = [
            {k: _jsonable(v) for k, v in row.items()} for row in rows
        ]
    if "programs" in present:
        columns = {c["name"] for c in inspector.get_columns("programs")}
        if "status" in columns:
            rows = bind.execute(
                sa.text("SELECT id, status FROM programs")
            ).mappings().all()
            payload["program_status"] = [dict(row) for row in rows]

    if not any(payload.values()):
        return  # nothing to lose (fresh install, or already migrated)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = archive_dir() / f"program-status-{stamp}.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived program status/stage_history rows to {dest}")


def _backfill_missing_steps(bind) -> None:
    """Give any program with zero steps the full built-in checklist,
    unticked — carries programs added before program_steps existed, or whose
    detail page was never opened (ensure_steps() only seeds lazily)."""
    program_ids = [
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT id FROM programs WHERE id NOT IN "
                "(SELECT DISTINCT program_id FROM program_steps)"
            )
        )
    ]
    if not program_ids:
        return
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


def upgrade() -> None:
    bind = op.get_bind()

    _archive_status_data(bind)
    _backfill_missing_steps(bind)

    with op.batch_alter_table('stage_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stage_history_program_id'))
    op.drop_table('stage_history')

    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.drop_column('status')


def downgrade() -> None:
    """Restores the schema only — the dropped rows are NOT restored."""
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'status',
                sa.String(length=40),
                nullable=False,
                server_default='researching',
            )
        )

    op.create_table(
        'stage_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('stage_history', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_stage_history_program_id'), ['program_id'], unique=False
        )
