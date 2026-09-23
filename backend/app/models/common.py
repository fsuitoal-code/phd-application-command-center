"""Shared helpers for ORM models."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive-UTC timestamp for SQLite default columns.

    SQLite has no native tz-aware type; we store UTC and treat all naive
    timestamps as UTC throughout the app.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
