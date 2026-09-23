"""The data directory must never be conjured out of a misconfiguration.

Twice, a wrong path produced a pristine empty database and an app that looked
like every program had been lost. These tests pin the behaviour that prevents
it: resolving a data directory that does not hold a database is an error, and
creating one is something you have to ask for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app import paths
from app.paths import DataDirNotInitialised, data_dir


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the session-wide override/init that conftest sets for every test."""
    monkeypatch.delenv(paths._ENV_OVERRIDE, raising=False)
    monkeypatch.delenv(paths._ENV_INIT, raising=False)


def test_missing_dir_raises_instead_of_creating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    target = tmp_path / "nowhere"
    monkeypatch.setenv(paths._ENV_OVERRIDE, str(target))

    with pytest.raises(DataDirNotInitialised) as excinfo:
        data_dir()

    assert not target.exists(), "the guard must not create the directory"
    # The message has to be actionable in a launcher dialog: it names the path
    # it resolved and where that came from.
    message = str(excinfo.value)
    assert str(target) in message
    assert paths._ENV_OVERRIDE in message


def test_existing_but_empty_dir_is_not_adopted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    """A path that exists but holds no database is still wrong."""
    target = tmp_path / "empty"
    target.mkdir()
    monkeypatch.setenv(paths._ENV_OVERRIDE, str(target))

    with pytest.raises(DataDirNotInitialised):
        data_dir()


def test_create_flag_initialises_and_marks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    target = tmp_path / "fresh"
    monkeypatch.setenv(paths._ENV_OVERRIDE, str(target))

    assert data_dir(create=True) == target
    assert (target / paths.MARKER_NAME).exists()
    # Once marked, an ordinary call succeeds without asking again.
    assert data_dir() == target


def test_init_env_var_also_permits_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    target = tmp_path / "viaenv"
    monkeypatch.setenv(paths._ENV_OVERRIDE, str(target))
    monkeypatch.setenv(paths._ENV_INIT, "1")

    assert data_dir() == target
    assert (target / paths.MARKER_NAME).exists()


def test_existing_database_without_marker_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    """Installs that predate the marker must not be locked out."""
    target = tmp_path / "legacy"
    target.mkdir()
    (target / paths.DB_FILENAME).write_bytes(b"")
    monkeypatch.setenv(paths._ENV_OVERRIDE, str(target))

    assert data_dir() == target


def test_unset_override_does_not_create_platform_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clean_env: None
) -> None:
    """The real hazard: no override at all, so the platform default is used.

    That default is where a forgotten environment variable sends a process, and
    it must not spring into existence there either.
    """
    monkeypatch.setattr(paths, "_platform_base", lambda: tmp_path / "platform")

    with pytest.raises(DataDirNotInitialised) as excinfo:
        data_dir()

    assert not (tmp_path / "platform").exists()
    assert "default location" in str(excinfo.value)
