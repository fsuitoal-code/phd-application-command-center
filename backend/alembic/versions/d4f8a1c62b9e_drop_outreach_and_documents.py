"""drop outreach drafting and the documents table

Outreach email drafting (``/faculty/{id}/outreach``) is removed: the user
writes their own outreach, same decision already made for SOP/CV generation.
``documents`` had no other writer left (``sop``/``cv`` kinds were already
legacy, written by nothing), so the whole table goes with it, and so does
``correspondence.document_id``, the FK that pointed into it -- the API never
actually set that column (``addCorrespondence`` has no ``document_id`` field),
so nothing meaningful is lost there.

DATA LOSS WARNING (Rule 10): before dropping, every ``documents`` row is
exported to ``<app-data>/archive/documents-<UTC stamp>.json``, along with any
non-null ``correspondence.document_id`` values (so a logged email that pointed
at a draft keeps that link legible), same pattern as
``1c6d9a2e4f81_remove_program_status.py``.

``downgrade()`` restores the schema only (empty ``documents`` table, restored
``correspondence.document_id`` column) -- the archived JSON is the way to get
the data back, not this migration.

Revision ID: d4f8a1c62b9e
Revises: 8a31535f5de3
Create Date: 2026-09-22
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4f8a1c62b9e'
down_revision: Union[str, None] = '8a31535f5de3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonable(value):
    if hasattr(value, "isoformat"):  # datetime or date
        return value.isoformat()
    return value


def _archive_documents(bind) -> None:
    """Export documents rows, and any correspondence->document links, before
    dropping them."""
    from app.paths import archive_dir

    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())

    payload: dict[str, list[dict]] = {}
    if "documents" in present:
        rows = bind.execute(sa.text("SELECT * FROM documents")).mappings().all()
        payload["documents"] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]
    if "correspondence" in present:
        columns = {c["name"] for c in inspector.get_columns("correspondence")}
        if "document_id" in columns:
            rows = bind.execute(
                sa.text(
                    "SELECT id, document_id FROM correspondence WHERE document_id IS NOT NULL"
                )
            ).mappings().all()
            if rows:
                payload["correspondence_document_links"] = [dict(row) for row in rows]

    if not any(payload.values()):
        return  # nothing to lose (fresh install, or already migrated)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = archive_dir() / f"documents-{stamp}.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived documents rows to {dest}")


def upgrade() -> None:
    bind = op.get_bind()

    _archive_documents(bind)

    with op.batch_alter_table('correspondence', schema=None) as batch_op:
        batch_op.drop_column('document_id')

    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_program_id'))
        batch_op.drop_index(batch_op.f('ix_documents_faculty_id'))
    op.drop_table('documents')


def downgrade() -> None:
    """Restores the schema only -- the dropped rows are NOT restored."""
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('faculty_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('mode', sa.String(length=40), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('requires_review', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['faculty_id'], ['faculty.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_documents_faculty_id'), ['faculty_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_documents_program_id'), ['program_id'], unique=False
        )

    with op.batch_alter_table('correspondence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('document_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_correspondence_document_id',
            'documents',
            ['document_id'],
            ['id'],
            ondelete='SET NULL',
        )
