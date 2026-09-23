"""app.migrate: snapshot-then-upgrade, and the cases where it must refuse."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory

from app import migrate
from app.paths import DB_FILENAME


@pytest.fixture()
def data_dir(tmp_path, monkeypatch) -> Path:
    """A fresh data directory of its own (conftest sets PHDTRACKER_INIT=1)."""
    monkeypatch.setenv("PHDTRACKER_DATA_DIR", str(tmp_path))
    return tmp_path


def _head_and_parent() -> tuple[str, str]:
    script = ScriptDirectory.from_config(migrate.alembic_config())
    head = script.get_current_head()
    return head, script.get_revision(head).down_revision


def _snapshots(data_dir: Path) -> list[Path]:
    return sorted((data_dir / "backups").glob("*.sqlite3"))


def _version(db_file: Path) -> str:
    conn = sqlite3.connect(db_file)
    try:
        return conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        conn.close()


def test_up_to_date_database_is_left_alone(data_dir):
    command.upgrade(migrate.alembic_config(), "head")

    assert migrate.main() == migrate.OK
    assert _snapshots(data_dir) == []


def test_pending_migration_is_snapshotted_then_applied(data_dir):
    head, parent = _head_and_parent()
    command.upgrade(migrate.alembic_config(), parent)

    assert migrate.main() == migrate.OK

    [snapshot] = _snapshots(data_dir)
    assert _version(snapshot) == parent
    assert _version(data_dir / DB_FILENAME) == head


def test_first_run_creates_the_database_without_a_snapshot(data_dir):
    head, _ = _head_and_parent()

    assert migrate.main() == migrate.OK
    assert _version(data_dir / DB_FILENAME) == head
    assert _snapshots(data_dir) == []


def test_uninitialised_data_dir_is_refused_and_not_created(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    monkeypatch.setenv("PHDTRACKER_DATA_DIR", str(missing))
    monkeypatch.delenv("PHDTRACKER_INIT")

    assert migrate.main() == migrate.NOT_INITIALISED
    assert not missing.exists()


def test_database_from_a_newer_version_is_refused(data_dir):
    command.upgrade(migrate.alembic_config(), "head")
    db = data_dir / DB_FILENAME
    conn = sqlite3.connect(db)
    conn.execute("UPDATE alembic_version SET version_num = 'ffffffffffff'")
    conn.commit()
    conn.close()

    assert migrate.main() == migrate.NEWER_DATABASE
    assert _version(db) == "ffffffffffff"
    assert _snapshots(data_dir) == []


def test_failed_snapshot_blocks_the_migration(data_dir, monkeypatch):
    _, parent = _head_and_parent()
    command.upgrade(migrate.alembic_config(), parent)

    def fail() -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.backup.snapshot_database", fail)

    assert migrate.main() == migrate.FAILED
    assert _version(data_dir / DB_FILENAME) == parent


def test_failed_upgrade_names_the_snapshot(data_dir, monkeypatch, capsys):
    _, parent = _head_and_parent()
    command.upgrade(migrate.alembic_config(), parent)

    def fail(*_args, **_kwargs) -> None:
        raise RuntimeError("migration exploded")

    monkeypatch.setattr(migrate.command, "upgrade", fail)

    assert migrate.main() == migrate.FAILED
    [snapshot] = _snapshots(data_dir)
    assert str(snapshot) in capsys.readouterr().out
    assert _version(data_dir / DB_FILENAME) == parent
