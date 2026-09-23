"""A research pass writes each cited fact as its own ProgramNote row,
source=researched + needs_human_verification=True -- the only path that
ever produces that state (see test_notes.py for everything else, which
defaults to already-confirmed).
"""

from __future__ import annotations


def test_research_pass_writes_notes_as_researched(client, monkeypatch):
    from app.claude.research import ResearchedNote, ResearchedProgram


    async def fake_research(query, official_url, interests):
        return ResearchedProgram(
            university="Anywhere U",
            notes=[
                ResearchedNote(
                    text="Fully funded for five years.",
                    quote="All admitted students receive five years of funding.",
                    source_url="https://cs.example.edu/funding",
                    source_label="funding page",
                ),
                ResearchedNote(
                    text="Cohort of about six students.",
                    quote="We admit roughly six students per year.",
                    source_url="https://cs.example.edu/admissions",
                    source_label="admissions page",
                ),
            ],
        )

    monkeypatch.setattr("app.claude.research.research_program", fake_research)

    r = client.post(
        "/api/programs/research",
        json={"query": "Anywhere U CS PhD", "official_url": "https://cs.example.edu"},
    )
    assert r.status_code == 201, r.text
    notes = r.json()["notes"]
    assert [n["text"] for n in notes] == [
        "Fully funded for five years.",
        "Cohort of about six students.",
    ]
    for n in notes:
        assert n["source"] == "researched"
        assert n["needs_human_verification"] is True
        assert n["quote"]
        # The URL is stored already fragment-decorated (quote_fragment_url).
        assert "#:~:text=" in n["source_url"]


def test_research_pass_with_no_notes_leaves_the_list_empty(client, monkeypatch):
    from app.claude.research import ResearchedProgram


    async def fake_research(query, official_url, interests):
        return ResearchedProgram(university="Anywhere U")

    monkeypatch.setattr("app.claude.research.research_program", fake_research)

    r = client.post(
        "/api/programs/research",
        json={"query": "Anywhere U CS PhD", "official_url": "https://cs.example.edu"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["notes"] == []
