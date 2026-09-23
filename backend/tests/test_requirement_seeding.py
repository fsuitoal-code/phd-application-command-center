"""Every new program gets the six built-in requirement fields — GRE, TOEFL,
Application Fee, Fee Waiver, Recommendation Letters, Essay Type — even with
no value known yet. Blank rows are flagged needs_human_verification until
research or the user fills them in.
"""

from __future__ import annotations

from app.models import Program, Requirement
from app.models.enums import BUILTIN_REQUIREMENT_KINDS
from app.routers.programs import _ensure_default_requirements


def test_manually_created_program_is_seeded_with_the_six_builtin_kinds(client):
    r = client.post(
        "/api/programs",
        json={"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"},
    )
    assert r.status_code == 201, r.text
    prog = r.json()
    assert [req["kind"] for req in prog["requirements"]] == BUILTIN_REQUIREMENT_KINDS
    for req in prog["requirements"]:
        assert req["value"] is None
        assert req["needs_human_verification"] is True
        assert req["source"] == "researched"


def test_ensure_default_requirements_fills_only_missing_kinds():
    program = Program(university="Test")
    program.requirements.append(
        Requirement(kind="gre", value="not required", sort_order=0)
    )
    _ensure_default_requirements(program)
    kinds = [r.kind for r in program.requirements]
    assert kinds == BUILTIN_REQUIREMENT_KINDS
    # the pre-existing gre row is untouched, not duplicated or overwritten
    gre = next(r for r in program.requirements if r.kind == "gre")
    assert gre.value == "not required"


def test_ensure_default_requirements_is_a_noop_when_all_present():
    program = Program(university="Test")
    for i, kind in enumerate(BUILTIN_REQUIREMENT_KINDS):
        program.requirements.append(Requirement(kind=kind, sort_order=i))
    _ensure_default_requirements(program)
    assert len(program.requirements) == len(BUILTIN_REQUIREMENT_KINDS)


def test_ensure_default_requirements_on_an_empty_program():
    program = Program(university="Test")
    _ensure_default_requirements(program)
    assert [r.kind for r in program.requirements] == BUILTIN_REQUIREMENT_KINDS
    assert [r.sort_order for r in program.requirements] == list(
        range(len(BUILTIN_REQUIREMENT_KINDS))
    )


def test_research_pass_fills_missing_builtin_kinds_without_duplicating_found_ones(
    client, monkeypatch
):
    from app.claude.research import ResearchedProgram, ResearchedRequirement


    async def fake_research(query, official_url):
        return ResearchedProgram(
            university="Anywhere U",
            requirements=[
                ResearchedRequirement(kind="gre", value="not required"),
                ResearchedRequirement(kind="rec_letters", value="3"),
            ],
        )

    monkeypatch.setattr("app.claude.research.research_program", fake_research)

    r = client.post(
        "/api/programs/research",
        json={"query": "Anywhere U CS PhD", "official_url": "https://cs.example.edu"},
    )
    assert r.status_code == 201, r.text
    reqs = r.json()["requirements"]
    assert [req["kind"] for req in reqs] == BUILTIN_REQUIREMENT_KINDS

    by_kind = {req["kind"]: req for req in reqs}
    assert by_kind["gre"]["value"] == "not required"
    assert by_kind["rec_letters"]["value"] == "3"
    # kinds the pass didn't find are still present, just blank
    assert by_kind["toefl"]["value"] is None
    assert by_kind["essay_type"]["value"] is None


def test_research_pass_appends_non_builtin_kinds_after_the_six(client, monkeypatch):
    from app.claude.research import ResearchedProgram, ResearchedRequirement


    async def fake_research(query, official_url):
        return ResearchedProgram(
            university="Anywhere U",
            requirements=[
                ResearchedRequirement(kind="other", value="writing sample required"),
                ResearchedRequirement(kind="toefl", value="required"),
            ],
        )

    monkeypatch.setattr("app.claude.research.research_program", fake_research)

    r = client.post(
        "/api/programs/research",
        json={"query": "Anywhere U CS PhD", "official_url": "https://cs.example.edu"},
    )
    assert r.status_code == 201, r.text
    reqs = r.json()["requirements"]
    # the six built-ins keep their fixed order first, regardless of the
    # order Claude returned them in, then the non-builtin "other" kind
    assert [req["kind"] for req in reqs] == BUILTIN_REQUIREMENT_KINDS + ["other"]
    assert reqs[-1]["value"] == "writing sample required"
