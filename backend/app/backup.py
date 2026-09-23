"""Pre-update SQLite backup helper (Rule 10).

Updating must snapshot the database to a timestamped file BEFORE running
migrations: a bad forward-only migration would otherwise risk the user's only
copy of their data. This module provides that snapshot and a
``python -m app.backup`` entry point.

Uses the stdlib ``sqlite3`` online-backup API, which produces a consistent copy
even while the database is in use (WAL-safe), rather than a raw file copy.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models.common import utcnow
from app.paths import backups_dir, database_path


def snapshot_database() -> Path | None:
    """Copy the live DB to ``backups/phdtracker-YYYYMMDD-HHMMSS.sqlite3``.

    Returns the backup path, or ``None`` if there is no database yet (first run
    — nothing to back up).
    """
    src = database_path()
    if not src.exists():
        return None

    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    dest = backups_dir() / f"phdtracker-{stamp}.sqlite3"

    source = sqlite3.connect(src)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    return dest


def main() -> None:
    dest = snapshot_database()
    if dest is None:
        print("No database found — nothing to back up.")
    else:
        print(f"Backed up database to {dest}")


if __name__ == "__main__":
    main()
