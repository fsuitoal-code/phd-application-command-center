"""Test the pre-update DB backup helper (Rule 10)."""

from __future__ import annotations

import sqlite3


def test_snapshot_produces_valid_sqlite(client):
    # Ensure there is some data to back up.
    client.post("/api/programs", json={"university": "Backup U"})

    from app.backup import snapshot_database

    dest = snapshot_database()
    assert dest is not None and dest.exists()

    con = sqlite3.connect(dest)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {r[0] for r in con.execute(
            "select name from sqlite_master where type='table'"
        )}
        assert "programs" in tables
    finally:
        con.close()
