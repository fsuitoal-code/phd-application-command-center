"""Bring the database schema up to date, snapshotting it first if anything changes.

    python -m app.migrate        (from backend/)

The launchers run this before starting the app and after pulling an update.
Migrations are forward-only (Rule 10): when the schema is already at head this
touches nothing; otherwise it snapshots the database with ``app.backup`` and
only then runs ``alembic upgrade head``. If the snapshot fails, nothing is
migrated.

Exit codes, which the launchers turn into plain-language messages:
  0  the database is up to date (already, or after migrating)
  1  the update failed; the output names the snapshot taken just before it
  2  the data directory isn't set up (see ``app.paths.data_dir``)
  3  the database was last updated by a newer version of the code
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.paths import DataDirNotInitialised, database_path, database_url

BACKEND_DIR = Path(__file__).resolve().parents[1]

OK, FAILED, NOT_INITIALISED, NEWER_DATABASE = 0, 1, 2, 3


def alembic_config() -> Config:
    """Alembic config for this checkout, usable from any working directory."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def current_revisions() -> set[str]:
    """The revisions the database is at; empty if it doesn't exist yet.

    Checks for the file first, because connecting would create an empty one.
    """
    if not database_path().exists():
        return set()
    engine = create_engine(database_url(), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            return set(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()


def main() -> int:
    try:
        db = database_path()
    except DataDirNotInitialised as exc:
        print(exc)
        return NOT_INITIALISED

    cfg = alembic_config()
    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())
    known = {rev.revision for rev in script.walk_revisions()}
    current = current_revisions()

    print(f"Database: {db}")
    unknown = current - known
    if unknown:
        print(
            "This database was last updated by a newer version of PhD Tracker "
            f"(revision {', '.join(sorted(unknown))}), so this copy of the code "
            "can't safely use it. Nothing was changed. Update the code rather "
            "than going back to an older version."
        )
        return NEWER_DATABASE
    if current == heads:
        print("Database is up to date.")
        return OK

    # Imported here, not at the top: it loads the models, which open the
    # database at import time and would fail before the check above could
    # explain an uninitialised data directory.
    from app.backup import snapshot_database

    try:
        snapshot = snapshot_database()  # None on first run: nothing to protect yet
    except Exception:
        traceback.print_exc()
        print("\nCouldn't back up the database, so it was not updated. Nothing was changed.")
        return FAILED
    if snapshot is not None:
        print(f"Backed up the database to:\n  {snapshot}")

    try:
        command.upgrade(cfg, "head")
        if current_revisions() != heads:
            raise RuntimeError("the upgrade finished but the database is not at the latest revision")
    except Exception:
        traceback.print_exc()
        print("\nThe database update did not complete.")
        if snapshot is not None:
            print(f"Your data from just before the update is safe in:\n  {snapshot}")
        return FAILED

    print("Database updated." if current else "Database created.")
    return OK


if __name__ == "__main__":
    sys.exit(main())
