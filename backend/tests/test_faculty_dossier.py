"""The per-faculty dossier: shortlist cap, tool boundary, endpoint, provenance.

No billed calls — the Claude contract is monkeypatched everywhere.
"""

from __future__ import annotations

import asyncio

import pytest

from app.claude.faculty_dossier import FacultyDossier, is_denied
from app.claude.research import ResearchedProgram
from app.config import settings


# ── Rule 3: the tool boundary ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "url",
    [
        "https://scholar.google.com/citations?user=abc",
        "https://scholar.google.co.uk/citations?user=abc",
        "https://www.google.com/search?q=professor",
        "https://www.bing.com/search?q=professor",
        "https://duckduckgo.com/?q=professor",
    ],
)
def test_search_engines_and_scholar_are_denied(url):
    """Rule 3 names Google Scholar; search results are for finding, not citing."""
    assert is_denied(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://industrial-engineering.uark.edu/directory/index.php",
        "https://vhil.stanford.edu/the-team",
        "https://www.amitgoldenberg.com/join-me",
        "https://news.cornell.edu/stories/2026/03/example",
        "https://www.nsf.gov/awardsearch/showAward?AWD_ID=1",
    ],
)
def test_primary_sources_are_allowed(url):
    assert is_denied(url) is False


def _callback():
    return __import__(
        "app.claude.faculty_dossier", fromlist=["_make_permission_callback"]
    )._make_permission_callback()


def test_callback_allows_search_blocks_scholar_and_other_tools():
    pytest.importorskip("claude_agent_sdk")
    can_use = _callback()

    async def run(tool, payload):
        return await can_use(tool, payload, None)

    allow = asyncio.run(run("WebSearch", {"query": "x"}))
    assert type(allow).__name__ == "PermissionResultAllow"

    denied = asyncio.run(
        run("WebFetch", {"url": "https://scholar.google.com/citations?user=a"})
    )
    assert type(denied).__name__ == "PermissionResultDeny"

    # Nothing outside the two web tools gets through — no Bash, no file access.
    blocked = asyncio.run(run("Bash", {"command": "ls"}))
    assert type(blocked).__name__ == "PermissionResultDeny"


# ── The shortlist cap ─────────────────────────────────────────────────────
def test_research_truncates_faculty_to_the_cap():
    """A prompt is a request; the cap is enforced whatever comes back."""
    found = ResearchedProgram(
        university="U",
        faculty=[{"name": f"Prof {i}"} for i in range(53)],
    )
    assert len(found.faculty) == settings.max_faculty_per_program
    # Truncated from the front, keeping the model's own relevance ordering.
    assert found.faculty[0].name == "Prof 0"


def test_research_keeps_a_short_list_intact():
    found = ResearchedProgram(university="U", faculty=[{"name": "Only One"}])
    assert len(found.faculty) == 1


# ── Assembling the markdown ───────────────────────────────────────────────
def _note(text="Runs the lab.", quote="She runs the lab.", url="https://lab.edu/about"):
    return {"text": text, "quote": quote, "source_url": url, "source_label": "lab about"}


def test_markdown_has_headings_and_citations():
    d = FacultyDossier(
        summary="A read.",
        sections=[
            {"heading": "Research", "items": [_note()]},
            {"heading": "Funding", "items": [_note("NSF funded.", "Funded by NSF.")]},
        ],
    )
    md = d.to_markdown()
    # The bottom line leads, as a plain paragraph: it is the model's own read,
    # and it should not be able to pass for a quoted fact.
    assert md.startswith("## Bottom line\nA read.")
    assert "## Research" in md
    assert "## Funding" in md
    # The citation jumps to the quoted sentence, and the quote is shown too.
    assert "#:~:text=" in md
    assert "> She runs the lab." in md


def test_uncited_items_and_empty_sections_are_dropped():
    """Rule 8: a claim with no source sentence is not a claim."""
    d = FacultyDossier(
        sections=[
            {"heading": "Research", "items": [_note()]},
            {"heading": "Funding", "items": [{"text": "Rich", "quote": "", "source_url": "", "source_label": ""}]},
        ]
    )
    md = d.to_markdown()
    assert "## Research" in md
    # An empty "Funding" heading would read as "no funding", which is not what
    # an unsourced claim means.
    assert "## Funding" not in md


# ── The endpoint ──────────────────────────────────────────────────────────
def _setup(client):
    prog = client.post("/api/programs", json={"university": "Test U"}).json()
    fac = client.post(
        f"/api/programs/{prog['id']}/faculty", json={"name": "Prof Y"}
    ).json()
    return prog, fac


def _fake_dossier():
    return FacultyDossier(
        summary="Mid-career, well funded, the open question is recruiting.",
        research_areas="queueing networks, healthcare operations",
        homepage_url="https://lab.edu/",
        sections=[{"heading": "Research", "items": [_note()]}],
    )


def test_research_stores_dossier_and_provenance(client, monkeypatch):
    prog, fac = _setup(client)

    async def fake(profile, faculty, program):
        return _fake_dossier()

    monkeypatch.setattr("app.claude.faculty_dossier.research_faculty", fake)
    r = client.post(f"/api/faculty/{fac['id']}/research")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "## Research" in body["dossier"]
    # Rule 8: which model wrote this, and when.
    assert body["dossier_model"]
    assert body["dossier_researched_at"]
    # Blank fields get backfilled from the pass.
    assert body["research_areas"] == "queueing networks, healthcare operations"
    assert body["homepage_url"] == "https://lab.edu/"


def test_research_does_not_overwrite_what_the_user_typed(client, monkeypatch):
    prog = client.post("/api/programs", json={"university": "Test U"}).json()
    fac = client.post(
        f"/api/programs/{prog['id']}/faculty",
        json={"name": "Prof Y", "research_areas": "mine, hand-written"},
    ).json()

    async def fake(profile, faculty, program):
        return _fake_dossier()

    monkeypatch.setattr("app.claude.faculty_dossier.research_faculty", fake)
    r = client.post(f"/api/faculty/{fac['id']}/research")
    assert r.json()["research_areas"] == "mine, hand-written"


def test_research_keeps_an_earlier_dossier_when_nothing_is_citable(client, monkeypatch):
    prog, fac = _setup(client)

    async def good(profile, faculty, program):
        return _fake_dossier()

    async def empty(profile, faculty, program):
        return FacultyDossier(sections=[])

    monkeypatch.setattr("app.claude.faculty_dossier.research_faculty", good)
    client.post(f"/api/faculty/{fac['id']}/research")

    monkeypatch.setattr("app.claude.faculty_dossier.research_faculty", empty)
    r = client.post(f"/api/faculty/{fac['id']}/research")
    assert r.status_code == 502

    detail = client.get(f"/api/programs/{prog['id']}").json()
    assert "## Research" in detail["faculty"][0]["dossier"]


def test_research_404_missing_faculty(client):
    assert client.post("/api/faculty/99999/research").status_code == 404


def test_research_needs_no_profile(client, monkeypatch):
    """A dossier is about the faculty member, so an empty profile is no bar.

    Demanding one would mean you cannot read about anyone until you have
    written about yourself, which is the wrong way round.
    """
    prog, fac = _setup(client)

    async def fake(profile, faculty, program):
        return _fake_dossier()

    monkeypatch.setattr("app.claude.faculty_dossier.research_faculty", fake)
    assert client.post(f"/api/faculty/{fac['id']}/research").status_code == 200
