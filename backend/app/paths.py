"""Cross-platform resolution of the app-data directory.

Rule 2 (data locality): a user's data (the SQLite
database and every generated document) lives OUTSIDE the git repo, in an
OS-appropriate app-data directory, so ``git pull`` can never touch it.

  * macOS   -> ~/Library/Application Support/PhDTracker/
  * Windows -> %LOCALAPPDATA%\\PhDTracker\\
  * Linux   -> $XDG_DATA_HOME/PhDTracker/ (or ~/.local/share/PhDTracker/)

Everything here uses ``pathlib`` only (Rule 9: cross-platform code, no
shell-specific logic in core code). An override via the ``PHDTRACKER_DATA_DIR``
environment variable exists for tests and for pointing at a populated DB copy
when verifying migrations (Rule 10).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "PhDTracker"
_ENV_OVERRIDE = "PHDTRACKER_DATA_DIR"
_ENV_INIT = "PHDTRACKER_INIT"
DB_FILENAME = "phdtracker.sqlite3"
MARKER_NAME = ".phdtracker-data-dir"


class DataDirNotInitialised(RuntimeError):
    """The resolved data directory does not hold a PhDTracker database.

    Raised instead of silently creating a fresh one. See ``data_dir``.
    """


def _platform_base() -> Path:
    """Return the OS-appropriate base directory for per-user application data."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local)
        return Path.home() / "AppData" / "Local"
    # Linux / other POSIX
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg)
    return Path.home() / ".local" / "share"


def _looks_initialised(base: Path) -> bool:
    """True if ``base`` is a directory we have already set up (or an old one)."""
    # The marker is written at init. The database check keeps directories that
    # predate the marker working, so an existing install is never locked out.
    return base.is_dir() and (
        (base / MARKER_NAME).exists() or (base / DB_FILENAME).exists()
    )


def data_dir(*, create: bool = False) -> Path:
    """The PhDTracker app-data directory. Never created by accident.

    Honours ``PHDTRACKER_DATA_DIR`` for tests / migration verification.

    This function used to ``mkdir`` unconditionally, which meant any
    misconfiguration -- an unset override, a typo, a redirected path -- produced
    a pristine empty database instead of an error, and the app came up looking
    like every program had vanished. It happened twice. So a *new* data
    directory is now only ever created deliberately: pass ``create=True`` (what
    ``python -m app.init_data_dir`` does) or set ``PHDTRACKER_INIT=1``.
    Otherwise a missing one is an error naming the path we resolved.
    """
    override = os.environ.get(_ENV_OVERRIDE)
    base = Path(override) if override else _platform_base() / APP_DIR_NAME

    if _looks_initialised(base):
        return base

    if create or os.environ.get(_ENV_INIT) == "1":
        base.mkdir(parents=True, exist_ok=True)
        marker = base / MARKER_NAME
        if not marker.exists():
            marker.write_text(
                "This directory holds your PhD Tracker database and documents.\n"
                "Deleting this marker makes the app refuse to start (it can no\n"
                "longer tell this directory apart from an empty one).\n",
                encoding="utf-8",
            )
        return base

    source = (
        f"the {_ENV_OVERRIDE} environment variable"
        if override
        else "the default location for this platform"
    )
    raise DataDirNotInitialised(
        f"No PhD Tracker data directory at:\n"
        f"  {base}\n"
        f"(resolved from {source}.)\n\n"
        f"Refusing to create an empty one -- if you already have a database "
        f"elsewhere, this usually means {_ENV_OVERRIDE} is unset or wrong, and "
        f"starting now would silently give you a blank app.\n\n"
        f"Check {_ENV_OVERRIDE} first. To set up a genuinely new database here, "
        f"run:\n"
        f"  python -m app.init_data_dir"
    )


def database_path() -> Path:
    """Absolute path to the per-machine SQLite database file."""
    return data_dir() / DB_FILENAME


def docs_dir() -> Path:
    """Directory for "My Docs" uploads — the CV, SOP, and any custom doc type."""
    d = data_dir() / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def notes_dir() -> Path:
    """Directory for files attached to "My Notes" entries."""
    d = data_dir() / "notes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def archive_dir() -> Path:
    """Directory for rows a forward-only migration drops, exported as JSON.

    A migration that drops a table takes data with it. The launcher already
    snapshots the whole database first, but a snapshot is only readable by
    restoring it; an archive file here keeps the dropped rows legible on their
    own (Rule 10).
    """
    d = data_dir() / "archive"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backups_dir() -> Path:
    """Directory for pre-migration timestamped DB snapshots (Rule 10)."""
    d = data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def database_url() -> str:
    """SQLAlchemy URL for the local SQLite database.

    ``as_posix()`` keeps the URL valid on Windows (forward slashes).
    """
    return f"sqlite:///{database_path().as_posix()}"
