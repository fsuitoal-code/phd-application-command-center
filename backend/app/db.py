"""SQLAlchemy engine, session factory, and declarative base.

Local SQLite, one file per machine, resolved to the app-data dir (see
``paths.py``). Models stay portable (Rule: avoid Postgres-only types) so the
same declarative base can later back Alembic migrations.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.paths import database_url


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


engine: Engine = create_engine(
    database_url(),
    # SQLite + threaded dev server: allow cross-thread use of connections.
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
    """Enforce foreign keys (off by default in SQLite)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
