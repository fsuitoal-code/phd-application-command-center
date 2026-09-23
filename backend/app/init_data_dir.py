"""Deliberately create a new PhD Tracker data directory.

``paths.data_dir()`` refuses to create one on its own, so that a wrong or
missing ``PHDTRACKER_DATA_DIR`` fails loudly instead of handing you a blank app
(see the note in ``paths.py``). This is the explicit way to say "yes, a new
database here is what I want" -- run once during setup:

    python -m app.init_data_dir

It only prepares the directory. The database itself is created by
``python -m app.migrate``, which setup and the launchers run next.
"""

from __future__ import annotations

import sys

from app.paths import DB_FILENAME, data_dir


def main() -> int:
    base = data_dir(create=True)
    db = base / DB_FILENAME
    print(f"Data directory ready: {base}")
    if db.exists():
        print(f"Existing database kept: {db}")
    else:
        print("No database yet - 'python -m app.migrate' creates one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
