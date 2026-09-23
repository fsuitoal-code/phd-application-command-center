"""my docs: replace cv upload/review and faculty fit with a doc-type registry

CV Review (per-program gap/recommendation advice against the uploaded CV) and
Faculty Fit assessment are both removed — the only two features that ever read
a CV's extracted text. In their place: "My Docs", a cycle-level registry of
doc *types* (CV and Statement of Purpose built in, plus any custom type the
user adds), each holding a plain list of uploaded files. Pure file storage,
no Claude involvement, no extracted text.

DATA LOSS WARNING (Rule 10): before dropping, every ``cv_uploads`` and
``cv_recommendations`` row, and any non-null ``faculty.fit_summary`` value, is
exported to ``<app-data>/archive/my-docs-migration-<UTC stamp>.json``, same
pattern as ``c4e1f07b52aa_cv_upload_replaces_experience.py`` /
``1c6d9a2e4f81_remove_program_status.py``. Uploaded CV files already on disk
under the old ``cvs/`` directory are left in place (unreferenced, not
deleted) — nothing destructive happens to them.

``downgrade()`` restores the schema only (empty ``cv_uploads`` /
``cv_recommendations``, ``faculty.fit_summary`` back as a nullable column) —
the archived JSON is how to get the data back, not this migration.

Revision ID: e1e940cbc676
Revises: 2b7e5f9a1c34
Create Date: 2026-09-21
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e1e940cbc676'
down_revision: Union[str, None] = '2b7e5f9a1c34'
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
    """Export cv_uploads, cv_recommendations and faculty.fit_summary before
    dropping them."""
    from app.paths import archive_dir

    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())

    payload: dict[str, list[dict]] = {}
    if "cv_uploads" in present:
        rows = bind.execute(sa.text("SELECT * FROM cv_uploads")).mappings().all()
        payload["cv_uploads"] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]
    if "cv_recommendations" in present:
        rows = bind.execute(sa.text("SELECT * FROM cv_recommendations")).mappings().all()
        payload["cv_recommendations"] = [
            {k: _jsonable(v) for k, v in row.items()} for row in rows
        ]
    if "faculty" in present:
        columns = {c["name"] for c in inspector.get_columns("faculty")}
        if "fit_summary" in columns:
            rows = (
                bind.execute(
                    sa.text(
                        "SELECT id, fit_summary FROM faculty "
                        "WHERE fit_summary IS NOT NULL"
                    )
                )
                .mappings()
                .all()
            )
            payload["faculty_fit_summary"] = [dict(row) for row in rows]

    if not any(payload.values()):
        return  # nothing to lose (fresh install, or already migrated)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = archive_dir() / f"my-docs-migration-{stamp}.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived cv_uploads/cv_recommendations/fit_summary rows to {dest}")


def upgrade() -> None:
    bind = op.get_bind()

    _archive_old_data(bind)

    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())

    if "cv_recommendations" in present:
        with op.batch_alter_table('cv_recommendations', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_cv_recommendations_program_id'))
            batch_op.drop_index(batch_op.f('ix_cv_recommendations_cv_upload_id'))
        op.drop_table('cv_recommendations')

    if "cv_uploads" in present:
        op.drop_table('cv_uploads')

    with op.batch_alter_table('faculty', schema=None) as batch_op:
        batch_op.drop_column('fit_summary')

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

    doc_types = sa.table(
        'doc_types',
        sa.column('id', sa.Integer),
        sa.column('key', sa.String),
        sa.column('title', sa.String),
        sa.column('is_custom', sa.Boolean),
        sa.column('sort_order', sa.Integer),
    )
    op.bulk_insert(
        doc_types,
        [
            {'key': key, 'title': title, 'is_custom': False, 'sort_order': order}
            for order, (key, title) in enumerate(BUILTIN_DOC_TYPES)
        ],
    )


def downgrade() -> None:
    """Restores the schema only — the dropped rows are NOT restored."""
    with op.batch_alter_table('doc_files', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_doc_files_doc_type_id'))
    op.drop_table('doc_files')
    op.drop_table('doc_types')

    with op.batch_alter_table('faculty', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fit_summary', sa.TEXT(), nullable=True))

    op.create_table(
        'cv_uploads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=300), nullable=True),
        sa.Column('filename', sa.String(length=500), nullable=True),
        sa.Column('stored_path', sa.String(length=1000), nullable=True),
        sa.Column('format', sa.String(length=20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'cv_recommendations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('cv_upload_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('theme', sa.String(length=300), nullable=False),
        sa.Column('detail', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('user_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cv_upload_id'], ['cv_uploads.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('cv_recommendations', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_cv_recommendations_program_id'), ['program_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_cv_recommendations_cv_upload_id'), ['cv_upload_id'], unique=False
        )
