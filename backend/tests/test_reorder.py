"""API tests for the manual program ordering (GET ?sort=manual + POST /reorder)."""

from __future__ import annotations


def _create(client, university: str, deadline: str | None = None):
    r = client.post("/api/programs", json={"university": university})
    assert r.status_code == 201, r.text
    prog = r.json()
    if deadline:
        client.post(f"/api/programs/{prog['id']}/deadlines", json={"date": deadline})
    return prog


def test_manual_order_wins_over_deadlines(client):
    """Dragging is the only ordering: a sooner deadline must not re-sort the list."""
    a = _create(client, "A", "2099-12-01")
    b = _create(client, "B", "2099-01-01")
    client.post("/api/programs/reorder", json={"ids": [a["id"], b["id"]]})

    assert [p["university"] for p in client.get("/api/programs").json()] == ["A", "B"]


def test_reorder_sets_sort_order_by_index(client):
    a = _create(client, "A", "2099-12-01")
    b = _create(client, "B", "2099-01-01")
    c = _create(client, "C")

    r = client.post(
        "/api/programs/reorder", json={"ids": [c["id"], a["id"], b["id"]]}
    )
    assert r.status_code == 200, r.text
    assert [p["university"] for p in r.json()] == ["C", "A", "B"]
    assert [p["sort_order"] for p in r.json()] == [0, 1, 2]

    listed = client.get("/api/programs").json()
    assert [p["university"] for p in listed] == ["C", "A", "B"]


def test_reorder_rejects_a_partial_list(client):
    a = _create(client, "A")
    _create(client, "B")
    r = client.post("/api/programs/reorder", json={"ids": [a["id"]]})
    assert r.status_code == 400


def test_reorder_rejects_unknown_ids(client):
    a = _create(client, "A")
    r = client.post("/api/programs/reorder", json={"ids": [a["id"], 99999]})
    assert r.status_code == 400


def test_reorder_rejects_duplicates(client):
    a = _create(client, "A")
    _create(client, "B")
    r = client.post("/api/programs/reorder", json={"ids": [a["id"], a["id"]]})
    assert r.status_code == 400


def test_a_new_program_is_appended_to_the_end(client):
    """A new program must land somewhere predictable, not at the top by accident."""
    a = _create(client, "A")
    b = _create(client, "B")
    client.post("/api/programs/reorder", json={"ids": [b["id"], a["id"]]})
    _create(client, "C")

    listed = client.get("/api/programs").json()
    assert [p["university"] for p in listed] == ["B", "A", "C"]
