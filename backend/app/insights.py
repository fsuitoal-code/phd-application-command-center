"""Deadline urgency + program staleness computation (surfacing only).

Pure functions over loaded ORM objects; no DB access, no schema. Thresholds come
from ``settings`` (config-driven). "Activity" is the latest of the program's
``updated_at`` and the newest timestamps across its completed steps and
My Notes — ticking a checklist step, edits, and writing a note all count.
(Adding a bare deadline/faculty row is not counted — a documented limitation.)
"""

from __future__ import annotations

from datetime import date, datetime

from app.config import settings
from app.models.enums import ApplicationStep


def urgency_for(next_deadline: date | None, today: date | None = None) -> tuple[str, int | None]:
    """Return (urgency, days_until_deadline) for a program's next deadline."""
    if next_deadline is None:
        return "none", None
    today = today or date.today()
    days = (next_deadline - today).days
    if days < 0:
        return "overdue", days
    if days <= settings.deadline_due_soon_days:
        return "due_soon", days
    if days <= settings.deadline_upcoming_days:
        return "upcoming", days
    return "none", days


def last_activity_of(program) -> datetime:
    """Newest activity timestamp across edits, ticked steps, My Notes."""
    candidates: list[datetime] = [program.updated_at]
    candidates += [s.completed_at for s in program.steps if s.completed_at]
    candidates += [n.updated_at for n in program.my_notes]
    return max(candidates)


def is_stale(program, next_deadline: date | None, today: date | None = None) -> bool:
    """Idle ≥ stale_days AND an upcoming deadline within the window AND active.

    A program whose "Submit application" step is already checked off is never
    stale; a program with no upcoming deadline is not flagged (per the chosen
    rule).
    """
    if any(
        s.key == ApplicationStep.SUBMITTED.value and s.completed
        for s in program.steps
    ):
        return False
    today = today or date.today()
    if next_deadline is None or next_deadline < today:
        return False
    if (next_deadline - today).days > settings.stale_deadline_window_days:
        return False
    idle_days = (today - last_activity_of(program).date()).days
    return idle_days >= settings.stale_days
