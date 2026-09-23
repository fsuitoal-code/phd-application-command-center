"""Test fixtures.

CRITICAL: point the app-data dir at a throwaway temp directory BEFORE importing
any app module, so tests never touch the real per-machine database (the whole
point of Rule 2 / Rule 10 caution). The engine in ``app.db`` binds to the URL at
import time, so the env override must be set first.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# ── Redirect data dir to a temp location before app imports ────────────────
_TMP = Path(tempfile.mkdtemp(prefix="phdtracker-test-"))
os.environ["PHDTRACKER_DATA_DIR"] = str(_TMP)
# The temp dir is empty, and data_dir() refuses to adopt a directory that holds
# no database (it would rather fail than hand the app a blank one). Tests want
# exactly that blank one, so say so explicitly.
os.environ["PHDTRACKER_INIT"] = "1"


def _run_migrations() -> None:
    from alembic import command

    from app.migrate import alembic_config

    command.upgrade(alembic_config(), "head")


@pytest.fixture(scope="session", autouse=True)
def _migrated_db() -> Iterator[None]:
    _run_migrations()
    yield
    # Best-effort cleanup of the temp data dir.
    import shutil

    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    """Truncate all tables between tests for isolation."""
    yield
    from sqlalchemy import delete

    from app.db import SessionLocal
    from app.models import (
        Deadline,
        DocFile,
        DocType,
        Faculty,
        Program,
        ProgramStep,
        Requirement,
    )

    with SessionLocal() as session:
        for model in (
            ProgramStep,
            Requirement,
            Deadline,
            DocFile,
            DocType,
            Faculty,
            Program,
        ):
            session.execute(delete(model))
        session.commit()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
