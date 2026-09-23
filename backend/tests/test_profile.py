"""Applicant profile get-or-create + update."""

from __future__ import annotations


def test_get_creates_single_profile(client):
    a = client.get("/api/profile").json()
    b = client.get("/api/profile").json()
    assert a["id"] == b["id"]  # same row, not a new one each call
    assert a["research_interests"] is None


def test_update_profile(client):
    client.get("/api/profile")
    r = client.put(
        "/api/profile",
        json={"target_degree": "PhD", "research_interests": "program synthesis"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["target_degree"] == "PhD"
    assert body["research_interests"] == "program synthesis"
    # Persisted.
    assert client.get("/api/profile").json()["research_interests"] == "program synthesis"
