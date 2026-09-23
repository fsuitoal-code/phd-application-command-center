"""API tests for adding, editing, deleting, and manually reordering a faculty
member's notes.

Purely user-typed (unlike a program's notes, no Claude contract writes one of
these), so there's no source/quote/confirm shape to test here -- just
text + sort_order, same CRUD/reorder pattern as program notes minus the
provenance fields.
"""

from __future__ import annotations


def _program(client, **over):
    payload = {"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"}
    payload.update(over)
    r = client.post("/api/programs", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _faculty(client, pid, **over):
    payload = {"name": "Prof X", "research_areas": "graph learning"}
    payload.update(over)
    r = client.post(f"/api/programs/{pid}/faculty", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _add_note(client, fid, **over):
    payload = {"text": "A note about this person"}
    payload.update(over)
    r = client.post(f"/api/faculty/{fid}/notes", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_new_faculty_has_no_notes(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    assert fac["notes"] == []


def test_added_note_has_no_provenance_fields(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    n = _add_note(client, fac["id"])
    assert set(n.keys()) == {"id", "faculty_id", "text", "sort_order"}


def test_new_notes_are_appended_in_sort_order(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    a = _add_note(client, fac["id"], text="First")
    b = _add_note(client, fac["id"], text="Second")
    assert b["sort_order"] > a["sort_order"]

    body = client.get(f"/api/programs/{prog['id']}").json()
    fac_body = next(f for f in body["faculty"] if f["id"] == fac["id"])
    assert [n["id"] for n in fac_body["notes"]] == [a["id"], b["id"]]


def test_add_rejects_blank_text(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    r = client.post(f"/api/faculty/{fac['id']}/notes", json={"text": "   "})
    assert r.status_code == 400


def test_edit_updates_text(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    n = _add_note(client, fac["id"], text="orig")

    r = client.patch(f"/api/faculty/{fac['id']}/notes/{n['id']}", json={"text": "corrected"})
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "corrected"


def test_edit_rejects_blank_text(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    n = _add_note(client, fac["id"])
    r = client.patch(f"/api/faculty/{fac['id']}/notes/{n['id']}", json={"text": "   "})
    assert r.status_code == 400


def test_note_of_another_faculty_is_404(client):
    prog = _program(client)
    a = _faculty(client, prog["id"], name="A")
    b = _faculty(client, prog["id"], name="B")
    n = _add_note(client, a["id"])
    r = client.patch(f"/api/faculty/{b['id']}/notes/{n['id']}", json={"text": "x"})
    assert r.status_code == 404


def test_delete_removes_the_note(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    n = _add_note(client, fac["id"])
    r = client.delete(f"/api/faculty/{fac['id']}/notes/{n['id']}")
    assert r.status_code == 204, r.text

    body = client.get(f"/api/programs/{prog['id']}").json()
    fac_body = next(f for f in body["faculty"] if f["id"] == fac["id"])
    assert fac_body["notes"] == []


def test_deleting_faculty_cascades_its_notes(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    _add_note(client, fac["id"])
    assert client.delete(f"/api/faculty/{fac['id']}").status_code == 204

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert body["faculty"] == []


def test_reorder_sets_sort_order_by_index(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    a = _add_note(client, fac["id"], text="A")
    b = _add_note(client, fac["id"], text="B")
    c = _add_note(client, fac["id"], text="C")
    reordered = [c["id"], a["id"], b["id"]]

    r = client.post(f"/api/faculty/{fac['id']}/notes/reorder", json={"ids": reordered})
    assert r.status_code == 200, r.text
    assert [n["id"] for n in r.json()] == reordered
    assert [n["sort_order"] for n in r.json()] == [0, 1, 2]

    body = client.get(f"/api/programs/{prog['id']}").json()
    fac_body = next(f for f in body["faculty"] if f["id"] == fac["id"])
    assert [n["id"] for n in fac_body["notes"]] == reordered


def test_reorder_rejects_a_partial_list(client):
    prog = _program(client)
    fac = _faculty(client, prog["id"])
    a = _add_note(client, fac["id"])
    _add_note(client, fac["id"], text="second")
    r = client.post(f"/api/faculty/{fac['id']}/notes/reorder", json={"ids": [a["id"]]})
    assert r.status_code == 400


def test_reorder_rejects_a_note_from_another_faculty(client):
    prog = _program(client)
    a = _faculty(client, prog["id"], name="A")
    b = _faculty(client, prog["id"], name="B")
    a_note = _add_note(client, a["id"])
    b_note = _add_note(client, b["id"])
    r = client.post(f"/api/faculty/{a['id']}/notes/reorder", json={"ids": [b_note["id"]]})
    assert r.status_code == 400
