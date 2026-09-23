"""Faculty delete + suggest-faculty prompt guard."""

from __future__ import annotations


def _program_with_faculty(client):
    prog = client.post("/api/programs", json={"university": "Test U"}).json()
    fac = client.post(
        f"/api/programs/{prog['id']}/faculty",
        json={"name": "Prof Y", "research_areas": "graph learning"},
    ).json()
    return prog, fac


def test_delete_faculty(client):
    """How an over-long list gets pruned; nothing deletes rows on its own."""
    prog, fac = _program_with_faculty(client)
    assert client.delete(f"/api/faculty/{fac['id']}").status_code == 204
    assert client.get(f"/api/programs/{prog['id']}").json()["faculty"] == []
    assert client.delete(f"/api/faculty/{fac['id']}").status_code == 404


def test_antifabrication_in_prompts():
    # Light guard that the anti-fabrication instruction is wired into prompts.
    from app.claude import faculty as f

    assert "ANTI-FABRICATION" in f._ANTIFAB
