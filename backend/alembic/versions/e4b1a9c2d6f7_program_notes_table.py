"""program notes become per-row, individually confirmable facts

Adds ``program_notes`` (Rule 8: source + needs_human_verification, same
pattern as requirements/deadlines) and DROPS ``programs.notes`` (the old
single markdown-blob column it replaces).

DATA LOSS WARNING (Rule 10): before dropping, every non-empty ``notes``
value is exported to ``<app-data>/archive/program-notes-<UTC stamp>.json``
(program_id -> raw text), then parsed into rows and inserted into
``program_notes``. The parser recognises the exact shapes the app itself
ever wrote: a cited bullet (``- {text} ([{label}]({url}))`` followed by a
``> {quote}`` line), an uncited bullet (``- {text}`` alone, from an older
fallback path), and plain prose (pre-bullet-contract rows) -- consecutive
prose lines collapse into one row. Migrated rows are backfilled to
confirmed/no-verification-needed, same reasoning as the deadline source
migration: don't retroactively flag content the user has already been
looking at as normal.

``downgrade()`` restores the ``notes`` column (empty) and drops
``program_notes`` -- it restores the schema, not the data. Re-import from
the archive JSON if the rows are ever needed back.

Revision ID: e4b1a9c2d6f7
Revises: b6a3f0e27c58
Create Date: 2026-09-21
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e4b1a9c2d6f7'
down_revision: Union[str, None] = 'b6a3f0e27c58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Older builds of _render_note left a stray trailing "." after the closing
#: "))" on some rows; tolerate it (and any trailing whitespace) rather than
#: falling through to the plain-bullet case and losing the citation.
_BULLET_WITH_LINK = re.compile(r"^-\s+(.*?)\s+\(\[([^\]]*)\]\(([^)]*)\)\)\.?\s*$")
_BULLET_PLAIN = re.compile(r"^-\s+(.*)$")
_QUOTE_LINE = re.compile(r"^>\s?(.*)$")


def _parse_notes(text: str) -> list[dict]:
    """Recover structured note items from previously-assembled markdown."""
    lines = text.split("\n")
    items: list[dict] = []
    prose_buffer: list[str] = []

    def flush_prose() -> None:
        if prose_buffer:
            joined = " ".join(line.strip() for line in prose_buffer if line.strip())
            if joined:
                items.append(
                    {"text": joined, "quote": None, "source_url": None, "source_label": None}
                )
            prose_buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        cited = _BULLET_WITH_LINK.match(line)
        if cited:
            flush_prose()
            quote = None
            if i + 1 < len(lines):
                qm = _QUOTE_LINE.match(lines[i + 1].rstrip())
                if qm:
                    quote = qm.group(1)
                    i += 1
            items.append(
                {
                    "text": cited.group(1),
                    "quote": quote,
                    "source_url": cited.group(3),
                    "source_label": cited.group(2),
                }
            )
            i += 1
            continue
        plain = _BULLET_PLAIN.match(line)
        if plain:
            flush_prose()
            items.append(
                {"text": plain.group(1), "quote": None, "source_url": None, "source_label": None}
            )
            i += 1
            continue
        prose_buffer.append(line)
        i += 1
    flush_prose()
    return items


def _archive_and_migrate_notes() -> None:
    from app.paths import archive_dir

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, notes FROM programs WHERE notes IS NOT NULL AND notes != ''")
    ).fetchall()
    if not rows:
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = {str(row.id): row.notes for row in rows}
    dest = archive_dir() / f"program-notes-{stamp}.json"
    dest.write_text(json.dumps(archive, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived {len(rows)} program notes value(s) to {dest}")

    insert = sa.text(
        "INSERT INTO program_notes "
        "(program_id, text, quote, source_url, source_label, source, "
        "needs_human_verification, sort_order) "
        "VALUES (:program_id, :text, :quote, :source_url, :source_label, "
        "'confirmed_by_program', 0, :sort_order)"
    )
    for row in rows:
        for order, item in enumerate(_parse_notes(row.notes)):
            bind.execute(insert, {"program_id": row.id, "sort_order": order, **item})


def upgrade() -> None:
    op.create_table(
        'program_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('quote', sa.Text(), nullable=True),
        sa.Column('source_url', sa.String(length=2000), nullable=True),
        sa.Column('source_label', sa.String(length=200), nullable=True),
        sa.Column('source', sa.String(length=40), nullable=False),
        sa.Column('needs_human_verification', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('program_notes', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_program_notes_program_id'), ['program_id'], unique=False
        )

    _archive_and_migrate_notes()

    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.drop_column('notes')


def downgrade() -> None:
    """Restores the schema only — migrated note rows are NOT restored."""
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))

    with op.batch_alter_table('program_notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_program_notes_program_id'))
    op.drop_table('program_notes')
