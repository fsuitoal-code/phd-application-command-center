"""Suggest-faculty endpoint: non-persistence and dedupe, Claude call monkeypatched."""

from __future__ import annotations

from app.claude.faculty import SuggestedFaculty, SuggestResult


def _program(client, **over):
    payload = {"university": "Test U", "portal_url": "https://cs.testu.edu"}
    payload.update(over)
    return client.post("/api/programs", json=payload).json()


def test_suggest_returns_without_persisting(client, monkeypatch):
    prog = _program(client)

    async def fake_suggest(program, official_url):
        assert official_url == "https://cs.testu.edu"  # defaulted from portal_url
        return SuggestResult(
            faculty=[SuggestedFaculty(name="Prof Z", research_areas="ML")],
            already_listed=["Prof Y"],
        )

    monkeypatch.setattr("app.claude.faculty.suggest_faculty", fake_suggest)
    r = client.post(f"/api/programs/{prog['id']}/suggest-faculty", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["faculty"][0]["name"] == "Prof Z"
    assert body["already_listed"] == ["Prof Y"]
    # NOT persisted as faculty rows.
    detail = client.get(f"/api/programs/{prog['id']}").json()
    assert detail["faculty"] == []


def test_suggest_requires_a_url(client, monkeypatch):
    prog = _program(client, portal_url=None)
    r = client.post(f"/api/programs/{prog['id']}/suggest-faculty", json={})
    assert r.status_code == 400


def test_suggestions_drop_people_already_listed():
    """A suggestion you already have wastes a slot in a billed pass; the
    match ignores accents, case and spacing ("Özlem" is "Ozlem")."""
    from app.claude.faculty import _drop_existing

    found = [
        SuggestedFaculty(name="Özlem  Ergun"),
        SuggestedFaculty(name="Prof New"),
        SuggestedFaculty(name="prof new"),
    ]
    result = _drop_existing(found, ["Ozlem Ergun"])
    assert [s.name for s in result.faculty] == ["Prof New"]
    # Reported by the program's own spelling, so the UI can name them.
    assert result.already_listed == ["Ozlem Ergun"]


def test_unparseable_answer_becomes_a_readable_502(client, monkeypatch):
    """A reply that isn't the JSON shape asked for surfaces as a sentence, not
    a parser or validator dump."""
    prog = _program(client)

    async def fake_run_text(prompt, options):
        return '{"faculty": [{"research_areas": "no name field"}]}'

    monkeypatch.setattr("app.claude.faculty._run_text", fake_run_text)
    r = client.post(f"/api/programs/{prog['id']}/suggest-faculty", json={})
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert "wasn't a list of faculty" in detail
    assert "validation error" not in detail.lower()


def test_prompt_allows_an_empty_answer(client, monkeypatch):
    """Without saying so, the model pads the list with weak matches."""
    prog = _program(client)
    seen = {}

    async def fake_run_text(prompt, options):
        seen["system"] = options.system_prompt
        return '{"faculty": []}'

    monkeypatch.setattr("app.claude.faculty._run_text", fake_run_text)
    r = client.post(f"/api/programs/{prog['id']}/suggest-faculty", json={})
    assert r.json() == {"faculty": [], "already_listed": []}
    assert '{"faculty": []} is a correct answer' in seen["system"]
