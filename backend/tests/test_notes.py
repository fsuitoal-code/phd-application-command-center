"""API tests for editing, deleting, and manually reordering a program's notes.

Notes are per-row facts now (see test_note_seeding.py for the research-pass
write path), same CRUD/reorder/confirm shape as requirements and deadlines.
A hand-added note has no citation, so it's already confirmed (nothing to
verify) -- only a Claude-researched note (one with a quote) ever shows the
verify badge.
"""

from __future__ import annotations


def _create(client, **over):
    payload = {"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"}
    payload.update(over)
    r = client.post("/api/programs", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _add_note(client, pid, **over):
    payload = {"text": "A fact about the program"}
    payload.update(over)
    r = client.post(f"/api/programs/{pid}/notes", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_new_program_has_no_notes(client):
    prog = _create(client)
    assert prog["notes"] == []


def test_added_note_defaults_to_confirmed(client):
    prog = _create(client)
    n = _add_note(client, prog["id"])
    assert n["source"] == "confirmed_by_program"
    assert n["needs_human_verification"] is False
    assert n["quote"] is None
    assert n["source_url"] is None


def test_new_notes_are_appended_in_sort_order(client):
    prog = _create(client)
    a = _add_note(client, prog["id"], text="First")
    b = _add_note(client, prog["id"], text="Second")
    assert b["sort_order"] > a["sort_order"]

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [n["id"] for n in body["notes"]] == [a["id"], b["id"]]


def test_add_rejects_blank_text(client):
    prog = _create(client)
    r = client.post(f"/api/programs/{prog['id']}/notes", json={"text": "   "})
    assert r.status_code == 400


def test_edit_updates_text(client):
    prog = _create(client)
    n = _add_note(client, prog["id"], text="orig")

    r = client.patch(
        f"/api/programs/{prog['id']}/notes/{n['id']}", json={"text": "corrected"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "corrected"


def test_editing_text_auto_confirms(client):
    prog = _create(client)
    n = _add_note(
        client, prog["id"], text="orig", source="researched", needs_human_verification=True,
    )
    assert n["source"] == "researched"

    r = client.patch(
        f"/api/programs/{prog['id']}/notes/{n['id']}", json={"text": "corrected"}
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["source"] == "confirmed_by_program"
    assert updated["needs_human_verification"] is False


def test_edit_with_explicit_source_is_not_overridden(client):
    prog = _create(client)
    n = _add_note(client, prog["id"])

    r = client.patch(
        f"/api/programs/{prog['id']}/notes/{n['id']}",
        json={"text": "corrected", "source": "researched"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "researched"


def test_edit_rejects_blank_text(client):
    prog = _create(client)
    n = _add_note(client, prog["id"])
    r = client.patch(f"/api/programs/{prog['id']}/notes/{n['id']}", json={"text": "   "})
    assert r.status_code == 400


def test_note_of_another_program_is_404(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    n = _add_note(client, a["id"])
    r = client.patch(f"/api/programs/{b['id']}/notes/{n['id']}", json={"text": "x"})
    assert r.status_code == 404


def test_delete_removes_the_note(client):
    prog = _create(client)
    n = _add_note(client, prog["id"])
    r = client.delete(f"/api/programs/{prog['id']}/notes/{n['id']}")
    assert r.status_code == 204, r.text

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert body["notes"] == []


def test_confirm_promotes_and_can_correct_text(client):
    prog = _create(client)
    n = _add_note(
        client, prog["id"], text="orig", source="researched", needs_human_verification=True,
    )

    r = client.post(
        f"/api/programs/{prog['id']}/notes/{n['id']}/confirm",
        json={"text": "corrected"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "confirmed_by_program"
    assert body["needs_human_verification"] is False
    assert body["text"] == "corrected"


def test_confirm_404_wrong_program(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    n = _add_note(client, a["id"])
    r = client.post(f"/api/programs/{b['id']}/notes/{n['id']}/confirm", json={})
    assert r.status_code == 404


def test_reorder_sets_sort_order_by_index(client):
    prog = _create(client)
    a = _add_note(client, prog["id"], text="A")
    b = _add_note(client, prog["id"], text="B")
    c = _add_note(client, prog["id"], text="C")
    reordered = [c["id"], a["id"], b["id"]]

    r = client.post(f"/api/programs/{prog['id']}/notes/reorder", json={"ids": reordered})
    assert r.status_code == 200, r.text
    assert [n["id"] for n in r.json()] == reordered
    assert [n["sort_order"] for n in r.json()] == [0, 1, 2]

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [n["id"] for n in body["notes"]] == reordered


def test_reorder_rejects_a_partial_list(client):
    prog = _create(client)
    a = _add_note(client, prog["id"])
    _add_note(client, prog["id"], text="second")
    r = client.post(
        f"/api/programs/{prog['id']}/notes/reorder", json={"ids": [a["id"]]}
    )
    assert r.status_code == 400


def test_reorder_rejects_a_note_from_another_program(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    a_note = _add_note(client, a["id"])
    b_note = _add_note(client, b["id"])
    r = client.post(
        f"/api/programs/{a['id']}/notes/reorder", json={"ids": [b_note["id"]]}
    )
    assert r.status_code == 400
