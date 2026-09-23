"""CV upload + review replaces materials generation

Adds ``cv_uploads`` (the user's real CV, cycle-level) and ``cv_recommendations``
(per-program gaps and advice), and DROPS the tables that only existed to feed
the SOP/CV generators: ``experience_bullets``, ``experience_roles``,
``education_entries`` and ``gap_dismissals``.

DATA LOSS WARNING (Rule 10): those four tables are dropped. Before dropping,
every row is exported to ``<app-data>/archive/experience-<UTC stamp>.json`` so
the content stays readable without restoring a database backup. The Update
launcher's ``python -m app.backup`` snapshot remains the full safety net.

``downgrade()`` recreates the four tables EMPTY — it restores the schema, not
the data. Re-import from the archive JSON if you ever need the rows back.

Revision ID: c4e1f07b52aa
Revises: 9b3f2c8ad514
Create Date: 2026-09-19
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c4e1f07b52aa'
down_revision: Union[str, None] = '9b3f2c8ad514'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Dropped in this order (children first) — the same order the archive uses.
_DROPPED = ["experience_bullets", "experience_roles", "education_entries", "gap_dismissals"]


def _archive_dropped_tables() -> None:
    """Write every row of the soon-to-be-dropped tables to a JSON file."""
    from app.paths import archive_dir

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())

    payload: dict[str, list[dict]] = {}
    for table in _DROPPED:
        if table not in present:
            continue
        rows = bind.execute(sa.text(f"SELECT * FROM {table}")).mappings().all()  # noqa: S608
        payload[table] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]

    if not any(payload.values()):
        return  # nothing to lose (fresh install or already-empty tables)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = archive_dir() / f"experience-{stamp}.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived dropped experience rows to {dest}")


def _jsonable(value):
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "isoformat"):  # date
        return value.isoformat()
    return value


def upgrade() -> None:
    op.create_table(
        'cv_uploads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=300), nullable=True),
        sa.Column('filename', sa.String(length=500), nullable=True),
        sa.Column('stored_path', sa.String(length=1000), nullable=True),
        sa.Column('format', sa.String(length=20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
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

    # Export before destroying — see the module docstring.
    _archive_dropped_tables()

    with op.batch_alter_table('gap_dismissals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gap_dismissals_program_id'))
    op.drop_table('gap_dismissals')
    with op.batch_alter_table('experience_bullets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_experience_bullets_role_id'))
        batch_op.drop_index(batch_op.f('ix_experience_bullets_program_id'))
    op.drop_table('experience_bullets')
    op.drop_table('experience_roles')
    op.drop_table('education_entries')


def downgrade() -> None:
    """Restores the schema only — the dropped rows are NOT restored."""
    op.create_table(
        'education_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution', sa.String(length=300), nullable=False),
        sa.Column('degree', sa.String(length=200), nullable=True),
        sa.Column('field', sa.String(length=200), nullable=True),
        sa.Column('start_year', sa.Integer(), nullable=True),
        sa.Column('end_year', sa.Integer(), nullable=True),
        sa.Column('gpa', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'experience_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('organization', sa.String(length=300), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'experience_bullets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=True),
        sa.Column('program_id', sa.Integer(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('themes', sa.JSON(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['experience_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('experience_bullets', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_experience_bullets_program_id'), ['program_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_experience_bullets_role_id'), ['role_id'], unique=False
        )
    op.create_table(
        'gap_dismissals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('theme', sa.String(length=300), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gap_dismissals', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gap_dismissals_program_id'), ['program_id'], unique=False
        )

    with op.batch_alter_table('cv_recommendations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cv_recommendations_cv_upload_id'))
        batch_op.drop_index(batch_op.f('ix_cv_recommendations_program_id'))
    op.drop_table('cv_recommendations')
    op.drop_table('cv_uploads')
