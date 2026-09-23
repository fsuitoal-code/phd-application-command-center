"""my notes replace correspondence

The Mail tab (logged emails + Claude extraction of requirement confirmations)
is replaced by "My Notes": a per-program list of free-text notes the user
drags into order. ``my_notes`` is created; ``correspondence`` is dropped.

DATA LOSS WARNING (Rule 10): nothing a user logged disappears from view. Every
``correspondence`` row is (1) exported to
``<app-data>/archive/correspondence-<UTC stamp>.json``, same pattern as
``d4f8a1c62b9e``, and (2) carried over as a My Notes entry for its program,
oldest first, so the email is still readable in the tab that replaced Mail.

``downgrade()`` restores the schema only (empty ``correspondence``); the
archived JSON is the way to get the original rows back.

Revision ID: a6c2e8d41f73
Revises: f3a7c1e9b204
Create Date: 2026-09-22
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a6c2e8d41f73'
down_revision: Union[str, None] = 'f3a7c1e9b204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonable(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _note_text(row) -> str:
    heading = f"Email {row['direction'] or 'logged'}"
    if row["occurred_at"]:
        heading += f" ({row['occurred_at']})"
    if row["subject"]:
        heading += f": {row['subject']}"
    parts = [heading]
    if (row["body"] or "").strip():
        parts.append(row["body"].strip())
    if (row["notes"] or "").strip():
        parts.append(f"Notes: {row['notes'].strip()}")
    return "\n\n".join(parts)


def _carry_over_correspondence(bind) -> None:
    from app.paths import archive_dir

    if "correspondence" not in sa.inspect(bind).get_table_names():
        return
    rows = bind.execute(
        sa.text("SELECT * FROM correspondence ORDER BY program_id, created_at, id")
    ).mappings().all()
    if not rows:
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = archive_dir() / f"correspondence-{stamp}.json"
    payload = {"correspondence": [{k: _jsonable(v) for k, v in r.items()} for r in rows]}
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived correspondence rows to {dest}")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    order: dict[int, int] = {}
    for row in rows:
        pid = row["program_id"]
        order[pid] = order.get(pid, -1) + 1
        bind.execute(
            sa.text(
                "INSERT INTO my_notes (program_id, text, sort_order, created_at, updated_at)"
                " VALUES (:pid, :text, :sort_order, :created_at, :updated_at)"
            ),
            {
                "pid": pid,
                "text": _note_text(row),
                "sort_order": order[pid],
                "created_at": row["created_at"] or now,
                "updated_at": row["created_at"] or now,
            },
        )


def upgrade() -> None:
    op.create_table(
        'my_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('my_notes', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_my_notes_program_id'), ['program_id'], unique=False
        )

    _carry_over_correspondence(op.get_bind())

    with op.batch_alter_table('correspondence', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_correspondence_program_id'))
        batch_op.drop_index(batch_op.f('ix_correspondence_faculty_id'))
    op.drop_table('correspondence')


def downgrade() -> None:
    """Restores the schema only: ``correspondence`` comes back empty, and
    ``my_notes`` (including any notes typed since) is dropped."""
    op.create_table(
        'correspondence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('faculty_id', sa.Integer(), nullable=True),
        sa.Column('direction', sa.String(length=20), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('occurred_at', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['faculty_id'], ['faculty.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('correspondence', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_correspondence_faculty_id'), ['faculty_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_correspondence_program_id'), ['program_id'], unique=False
        )

    with op.batch_alter_table('my_notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_my_notes_program_id'))
    op.drop_table('my_notes')
