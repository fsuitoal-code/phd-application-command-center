"""Migration 37185aa3f20d: archive a filled-in applicant profile, then drop it."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command

from app import migrate
from app.paths import DB_FILENAME

REVISION = "37185aa3f20d"
PARENT = "b91f4d7c2a58"


@pytest.fixture()
def db(tmp_path, monkeypatch) -> Path:
    """A database of its own, one step before the drop."""
    monkeypatch.setenv("PHDTRACKER_DATA_DIR", str(tmp_path))
    command.upgrade(migrate.alembic_config(), PARENT)
    return tmp_path / DB_FILENAME


def _insert_profile(db: Path, **fields: str) -> None:
    columns = ["created_at", "updated_at", *fields]
    values = ["2026-09-19 01:33:16", "2026-09-19 01:33:16", *fields.values()]
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            f"INSERT INTO applicant_profile ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def _tables(db: Path) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def _archives(db: Path) -> list[Path]:
    return sorted((db.parent / "archive").glob("applicant-profile-*.json"))


def test_filled_in_profile_is_archived_then_dropped(db):
    _insert_profile(db, target_degree="PhD", research_interests="program synthesis")

    command.upgrade(migrate.alembic_config(), REVISION)

    assert "applicant_profile" not in _tables(db)
    [archive] = _archives(db)
    [row] = json.loads(archive.read_text(encoding="utf-8"))["applicant_profile"]
    assert row["research_interests"] == "program synthesis"
    assert row["target_degree"] == "PhD"


def test_empty_profile_is_dropped_without_an_archive(db):
    _insert_profile(db, keywords="   ")  # whitespace is not content

    command.upgrade(migrate.alembic_config(), REVISION)

    assert "applicant_profile" not in _tables(db)
    assert _archives(db) == []
