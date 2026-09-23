"""Every new program gets an Application deadline, even with no date known
yet — a manual add starts with none at all, and a research pass may not
find one. The deadline shows "No deadline" (date is nullable) until the
user fills one in.
"""

from __future__ import annotations

from app.models import Deadline, Program
from app.routers.programs import _ensure_application_deadline


def test_manually_created_program_is_seeded_with_an_application_deadline(client):
    r = client.post(
        "/api/programs",
        json={"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"},
    )
    assert r.status_code == 201, r.text
    prog = r.json()
    assert len(prog["deadlines"]) == 1
    seeded = prog["deadlines"][0]
    assert seeded["type"] == "application"
    assert seeded["date"] is None
    # Nothing was researched for a blank placeholder, so it's already
    # confirmed rather than flagged for verification.
    assert seeded["source"] == "confirmed_by_program"
    assert seeded["needs_human_verification"] is False


def test_ensure_application_deadline_adds_one_when_none_exists():
    program = Program(university="Test")
    program.deadlines.append(Deadline(type="funding", date=None, sort_order=0))
    _ensure_application_deadline(program)
    assert [d.type for d in program.deadlines] == ["funding", "application"]
    assert program.deadlines[-1].date is None


def test_ensure_application_deadline_is_a_noop_when_one_already_exists():
    program = Program(university="Test")
    program.deadlines.append(Deadline(type="Application", date=None, sort_order=0))
    _ensure_application_deadline(program)
    assert len(program.deadlines) == 1


def test_ensure_application_deadline_on_an_empty_program():
    program = Program(university="Test")
    _ensure_application_deadline(program)
    assert len(program.deadlines) == 1
    assert program.deadlines[0].type == "application"
    assert program.deadlines[0].sort_order == 0


def test_research_pass_writes_deadlines_as_researched(client, monkeypatch):
    from app.claude.research import ResearchedDeadline, ResearchedProgram

    async def fake_research(query, official_url, interests):
        return ResearchedProgram(
            university="Anywhere U",
            deadlines=[ResearchedDeadline(type="funding", date="2099-01-01")],
        )

    monkeypatch.setattr("app.claude.research.research_program", fake_research)

    r = client.post(
        "/api/programs/research",
        json={"query": "Anywhere U CS PhD", "official_url": "https://cs.example.edu"},
    )
    assert r.status_code == 201, r.text
    deadlines = r.json()["deadlines"]
    found = next(d for d in deadlines if d["date"] == "2099-01-01")
    assert found["source"] == "researched"
    assert found["needs_human_verification"] is True
    # The auto-seeded placeholder (nothing found for it) stays confirmed.
    placeholder = next(d for d in deadlines if d["date"] is None)
    assert placeholder["source"] == "confirmed_by_program"
