"""doc_types become per-program, not cycle-level

My Docs shipped as one shared CV/SOP/custom-doc registry for the whole cycle
(``e1e940cbc676``). The user wants it relocated into each program's own tabs
instead, with each program's documents independent of every other's — a CV or
SOP tailored to one program never shows up on another's. This adds
``doc_types.program_id`` and re-seeds ``BUILTIN_DOC_TYPES`` per existing
program, same backfill pattern ``1c6d9a2e4f81`` used for ``program_steps``.

DATA LOSS WARNING (Rule 10): before dropping, every ``doc_types`` and
``doc_files`` row is exported to
``<app-data>/archive/my-docs-per-program-<UTC stamp>.json`` (today's real dev
database only has the two empty built-in rows from the prior migration, but
the archive runs unconditionally, same as every migration in this file's
lineage). Files already on disk under ``paths.docs_dir()`` are left in place.

``downgrade()`` restores the schema only (empty, cycle-level ``doc_types``
with no ``program_id``) — the archived JSON is how to get the data back, not
this migration.

Revision ID: 8a31535f5de3
Revises: e1e940cbc676
Create Date: 2026-09-22
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '8a31535f5de3'
down_revision: Union[str, None] = 'e1e940cbc676'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Kept literal rather than imported from app.models.enums: a migration must
# describe the schema at this revision, not follow later edits to the enum.
BUILTIN_DOC_TYPES = [
    ("cv", "CV"),
    ("sop", "Statement of Purpose"),
]


def _jsonable(value):
    if hasattr(value, "isoformat"):  # datetime or date
        return value.isoformat()
    return value


def _archive_old_data(bind) -> None:
    from app.paths import archive_dir

    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())

    payload: dict[str, list[dict]] = {}
    if "doc_types" in present:
        rows = bind.execute(sa.text("SELECT * FROM doc_types")).mappings().all()
        payload["doc_types"] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]
    if "doc_files" in present:
        rows = bind.execute(sa.text("SELECT * FROM doc_files")).mappings().all()
        payload["doc_files"] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]

    if not any(payload.values()):
        return  # nothing to lose (fresh install, or already migrated)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = archive_dir() / f"my-docs-per-program-{stamp}.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived doc_types/doc_files rows to {dest}")


def upgrade() -> None:
    bind = op.get_bind()

    _archive_old_data(bind)

    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())

    if "doc_files" in present:
        with op.batch_alter_table('doc_files', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_doc_files_doc_type_id'))
        op.drop_table('doc_files')

    if "doc_types" in present:
        op.drop_table('doc_types')

    op.create_table(
        'doc_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=60), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('is_custom', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('doc_types', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_doc_types_program_id'), ['program_id'], unique=False
        )

    op.create_table(
        'doc_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doc_type_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('stored_path', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['doc_type_id'], ['doc_types.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('doc_files', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_doc_files_doc_type_id'), ['doc_type_id'], unique=False
        )

    # Backfill: every existing program gets the two built-in types, same
    # pattern 1c6d9a2e4f81 used for program_steps.
    program_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM programs"))]
    if program_ids:
        doc_types = sa.table(
            'doc_types',
            sa.column('program_id', sa.Integer),
            sa.column('key', sa.String),
            sa.column('title', sa.String),
            sa.column('is_custom', sa.Boolean),
            sa.column('sort_order', sa.Integer),
        )
        op.bulk_insert(
            doc_types,
            [
                {
                    'program_id': pid,
                    'key': key,
                    'title': title,
                    'is_custom': False,
                    'sort_order': order,
                }
                for pid in program_ids
                for order, (key, title) in enumerate(BUILTIN_DOC_TYPES)
            ],
        )


def downgrade() -> None:
    """Restores the schema only — the dropped rows are NOT restored."""
    with op.batch_alter_table('doc_files', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_doc_files_doc_type_id'))
    op.drop_table('doc_files')

    with op.batch_alter_table('doc_types', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_doc_types_program_id'))
    op.drop_table('doc_types')

    op.create_table(
        'doc_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=60), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('is_custom', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'doc_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doc_type_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('stored_path', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['doc_type_id'], ['doc_types.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('doc_files', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_doc_files_doc_type_id'), ['doc_type_id'], unique=False
        )
