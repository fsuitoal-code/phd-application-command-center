"""rename and prune built-in steps

Revision ID: 9a14f8506800
Revises: e2c5d80a1f64
Create Date: 2026-09-21

Retires two built-in steps (``researched`` — a generic catch-all — and
``recommenders`` — cycle-level, not program-level, see
docs/phase-8-cycle-schema.md), adds a new one (``faculty_outreach``, split out
from researching who the faculty are), and relabels the rest so the checklist
reads as concrete actions rather than section headers. See CLAUDE.md's
``program_steps`` entry for the final seven.

Every ``completed`` flag on the two retired steps is verified false in
production before writing this migration, so nothing is lost by dropping them.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a14f8506800'
down_revision: Union[str, None] = 'e2c5d80a1f64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Kept literal rather than imported from app.models.enums: a migration must
# describe the schema at this revision, not follow later edits to the enum.
RELABEL = {
    "requirements": "Researched requirements",
    "deadlines": "Researched deadlines",
    "faculty": "Researched faculty",
    "sop": "Essays",
    "cv": "Polish CV",
    "submitted": "Submit application",
}
RETIRED_KEYS = ("researched", "recommenders")
NEW_STEP = ("faculty_outreach", "Reach out to faculty")
CANONICAL_ORDER = [
    "requirements", "deadlines", "faculty", "faculty_outreach", "sop", "cv", "submitted",
]


def _resequence(bind: sa.engine.Connection, program_ids: list[int], canonical: list[str]) -> None:
    """Built-ins in ``canonical`` order, then any custom steps in their previous
    relative order — matches how ``ensure_steps``/the reorder endpoint lay a
    program's steps out, so an upgraded program's chips read left to right the
    same as a freshly created one, dragged order aside."""
    for pid in program_ids:
        rows = bind.execute(
            sa.text(
                "SELECT id, key, is_custom, sort_order FROM program_steps WHERE program_id = :pid"
            ),
            {"pid": pid},
        ).fetchall()
        builtins = sorted((r for r in rows if not r[2]), key=lambda r: canonical.index(r[1]))
        customs = sorted((r for r in rows if r[2]), key=lambda r: r[3])
        for index, row in enumerate([*builtins, *customs]):
            bind.execute(
                sa.text("UPDATE program_steps SET sort_order = :o WHERE id = :id"),
                {"o": index, "id": row[0]},
            )


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text("DELETE FROM program_steps WHERE is_custom = 0 AND key IN :keys").bindparams(
            sa.bindparam("keys", expanding=True)
        ),
        {"keys": list(RETIRED_KEYS)},
    )

    for key, label in RELABEL.items():
        bind.execute(
            sa.text(
                "UPDATE program_steps SET label = :label WHERE is_custom = 0 AND key = :key"
            ),
            {"label": label, "key": key},
        )

    # Only programs that already had a materialised checklist get the new step
    # inserted directly — a program with zero rows (added after this code
    # shipped but before the migration ran) is left alone for `ensure_steps` to
    # fill from the now-updated BUILTIN_STEPS on its next load.
    program_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT DISTINCT program_id FROM program_steps"))
    ]
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
        key, label = NEW_STEP
        op.bulk_insert(
            steps,
            [
                {
                    'program_id': pid,
                    'key': key,
                    'label': label,
                    'completed': False,
                    'completed_at': None,
                    'sort_order': 0,  # placeholder; _resequence fixes this up
                    'is_custom': False,
                }
                for pid in program_ids
            ],
        )

    _resequence(bind, program_ids, CANONICAL_ORDER)


def downgrade() -> None:
    bind = op.get_bind()

    reverse_relabel = {
        "requirements": "Requirements",
        "deadlines": "Deadlines",
        "faculty": "Faculty",
        "sop": "SOP",
        "cv": "CV",
        "submitted": "Submitted",
    }
    for key, label in reverse_relabel.items():
        bind.execute(
            sa.text(
                "UPDATE program_steps SET label = :label WHERE is_custom = 0 AND key = :key"
            ),
            {"label": label, "key": key},
        )

    bind.execute(
        sa.text(
            "DELETE FROM program_steps WHERE is_custom = 0 AND key = 'faculty_outreach'"
        )
    )

    program_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT DISTINCT program_id FROM program_steps"))
    ]
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
                    'sort_order': 0,  # placeholder; the resequence below fixes this up
                    'is_custom': False,
                }
                for pid in program_ids
                for key, label in (("researched", "Researched"), ("recommenders", "Recommenders"))
            ],
        )

    reverse_canonical = [
        "researched", "requirements", "deadlines", "faculty", "sop", "cv", "recommenders", "submitted",
    ]
    _resequence(bind, program_ids, reverse_canonical)
