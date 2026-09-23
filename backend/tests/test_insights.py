"""Pure urgency/staleness computation."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.insights import is_stale, last_activity_of, urgency_for


class _FakeStep:
    def __init__(self, key, completed=False, completed_at=None):
        self.key = key
        self.completed = completed
        self.completed_at = completed_at


class _FakeProgram:
    def __init__(self, updated_at=None, steps=None):
        self.updated_at = updated_at or datetime(2020, 1, 1)
        self.steps = steps or []
        self.my_notes = []


def test_urgency_boundaries():
    today = date(2026, 1, 1)
    assert urgency_for(None, today) == ("none", None)
    assert urgency_for(today - timedelta(days=1), today)[0] == "overdue"
    assert urgency_for(today, today)[0] == "due_soon"
    assert urgency_for(today + timedelta(days=14), today)[0] == "due_soon"
    assert urgency_for(today + timedelta(days=15), today)[0] == "upcoming"
    assert urgency_for(today + timedelta(days=45), today)[0] == "upcoming"
    assert urgency_for(today + timedelta(days=46), today)[0] == "none"
    assert urgency_for(today + timedelta(days=5), today)[1] == 5


def test_last_activity_picks_newest():
    p = _FakeProgram(updated_at=datetime(2020, 1, 1))
    p.steps = [_FakeStep("requirements", completed=True, completed_at=datetime(2026, 6, 1))]
    assert last_activity_of(p) == datetime(2026, 6, 1)


def test_is_stale_true_when_idle_and_looming_and_active():
    today = date(2026, 6, 1)
    p = _FakeProgram(updated_at=datetime(2026, 1, 1))  # idle > 21d
    assert is_stale(p, today + timedelta(days=30), today) is True


def test_is_stale_false_when_submitted_step_completed():
    today = date(2026, 6, 1)
    p = _FakeProgram(
        updated_at=datetime(2026, 1, 1),
        steps=[_FakeStep("submitted", completed=True)],
    )
    assert is_stale(p, today + timedelta(days=30), today) is False


def test_is_stale_false_without_upcoming_deadline():
    today = date(2026, 6, 1)
    p = _FakeProgram(updated_at=datetime(2026, 1, 1))
    assert is_stale(p, None, today) is False
    assert is_stale(p, today - timedelta(days=1), today) is False  # past deadline


def test_is_stale_false_when_recently_active():
    today = date(2026, 6, 1)
    p = _FakeProgram(updated_at=datetime(2026, 5, 30))  # 2 days ago
    assert is_stale(p, today + timedelta(days=10), today) is False


def test_is_stale_false_when_deadline_beyond_window():
    today = date(2026, 6, 1)
    p = _FakeProgram(updated_at=datetime(2026, 1, 1))
    assert is_stale(p, today + timedelta(days=90), today) is False  # > 60d window
