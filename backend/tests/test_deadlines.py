"""API tests for editing, deleting, and manually reordering a program's deadlines.

Deadlines used to always display sorted by date; they now carry their own
sort_order (same pattern as program_steps) so the user can drag them into
whatever order they want, independent of date.

`type` is free text, not a fixed enum — the UI offers common cases as
suggestions, but a program's own deadline can be labelled anything.

Every new program is also seeded with an Application deadline (see
test_deadline_seeding.py) — unrelated to what these CRUD/reorder tests
exercise, so `_create` strips it to start from a clean slate.
"""

from __future__ import annotations


def _create(client, **over):
    payload = {"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"}
    payload.update(over)
    r = client.post("/api/programs", json=payload)
    assert r.status_code == 201, r.text
    prog = r.json()
    for d in prog["deadlines"]:
        client.delete(f"/api/programs/{prog['id']}/deadlines/{d['id']}")
    prog["deadlines"] = []
    return prog


def _add_deadline(client, pid, **over):
    payload = {"type": "application", "date": "2099-01-01"}
    payload.update(over)
    r = client.post(f"/api/programs/{pid}/deadlines", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_new_deadlines_are_appended_in_sort_order(client):
    prog = _create(client)
    a = _add_deadline(client, prog["id"], date="2099-01-01")
    b = _add_deadline(client, prog["id"], date="2099-02-01")
    assert b["sort_order"] > a["sort_order"]

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [d["id"] for d in body["deadlines"]] == [a["id"], b["id"]]


def test_edit_updates_only_provided_fields(client):
    prog = _create(client)
    d = _add_deadline(client, prog["id"], type="application", date="2099-01-01", notes="orig")

    r = client.patch(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}", json={"date": "2099-03-01"}
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["date"] == "2099-03-01"
    assert updated["type"] == "application"
    assert updated["notes"] == "orig"


def test_type_accepts_arbitrary_free_text(client):
    prog = _create(client)
    d = _add_deadline(client, prog["id"], type="Portfolio review")
    assert d["type"] == "Portfolio review"

    r = client.patch(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}",
        json={"type": "Interview scheduling window"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "Interview scheduling window"


def test_add_blank_type_falls_back_to_application(client):
    prog = _create(client)
    d = _add_deadline(client, prog["id"], type="   ")
    assert d["type"] == "application"


def test_edit_rejects_a_blank_type(client):
    prog = _create(client)
    d = _add_deadline(client, prog["id"])
    r = client.patch(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}", json={"type": "   "}
    )
    assert r.status_code == 400


def test_edit_type_and_notes(client):
    prog = _create(client)
    d = _add_deadline(client, prog["id"])

    r = client.patch(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}",
        json={"type": "funding", "notes": "new note"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "funding"
    assert r.json()["notes"] == "new note"


def test_edit_can_explicitly_clear_notes(client):
    prog = _create(client)
    d = _add_deadline(client, prog["id"], notes="orig")

    r = client.patch(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}", json={"notes": None}
    )
    assert r.status_code == 200, r.text
    assert r.json()["notes"] is None


def test_added_deadline_defaults_to_confirmed(client):
    # Typed in by hand -- there is nothing to verify, unlike a fact an
    # actual research pass writes (source=researched).
    prog = _create(client)
    d = _add_deadline(client, prog["id"])
    assert d["source"] == "confirmed_by_program"
    assert d["needs_human_verification"] is False


def test_editing_date_auto_confirms(client):
    prog = _create(client)
    d = _add_deadline(
        client, prog["id"], date="2099-01-01",
        source="researched", needs_human_verification=True,
    )
    assert d["source"] == "researched"

    r = client.patch(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}", json={"date": "2099-03-01"}
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["source"] == "confirmed_by_program"
    assert updated["needs_human_verification"] is False


def test_editing_type_alone_also_auto_confirms(client):
    prog = _create(client)
    d = _add_deadline(
        client, prog["id"], source="researched", needs_human_verification=True,
    )

    r = client.patch(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}", json={"type": "funding"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "confirmed_by_program"


def test_edit_with_explicit_source_is_not_overridden(client):
    prog = _create(client)
    d = _add_deadline(client, prog["id"])

    r = client.patch(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}",
        json={"date": "2099-03-01", "source": "researched"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "researched"


def test_confirm_promotes_and_can_correct_the_date(client):
    prog = _create(client)
    d = _add_deadline(
        client, prog["id"], date="2099-01-01",
        source="researched", needs_human_verification=True,
    )

    r = client.post(
        f"/api/programs/{prog['id']}/deadlines/{d['id']}/confirm",
        json={"date": "2099-02-15"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "confirmed_by_program"
    assert body["needs_human_verification"] is False
    assert body["date"] == "2099-02-15"


def test_confirm_404_wrong_program(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    d = _add_deadline(client, a["id"])
    r = client.post(f"/api/programs/{b['id']}/deadlines/{d['id']}/confirm", json={})
    assert r.status_code == 404


def test_deadline_of_another_program_is_404(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    d = _add_deadline(client, a["id"])
    r = client.patch(f"/api/programs/{b['id']}/deadlines/{d['id']}", json={"notes": "x"})
    assert r.status_code == 404


def test_delete_removes_the_deadline(client):
    prog = _create(client)
    d = _add_deadline(client, prog["id"])
    r = client.delete(f"/api/programs/{prog['id']}/deadlines/{d['id']}")
    assert r.status_code == 204, r.text

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert body["deadlines"] == []


def test_reorder_sets_sort_order_by_index(client):
    prog = _create(client)
    a = _add_deadline(client, prog["id"], date="2099-01-01")
    b = _add_deadline(client, prog["id"], date="2099-02-01")
    c = _add_deadline(client, prog["id"], date="2099-03-01")
    reordered = [c["id"], a["id"], b["id"]]

    r = client.post(f"/api/programs/{prog['id']}/deadlines/reorder", json={"ids": reordered})
    assert r.status_code == 200, r.text
    assert [d["id"] for d in r.json()] == reordered
    assert [d["sort_order"] for d in r.json()] == [0, 1, 2]

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [d["id"] for d in body["deadlines"]] == reordered


def test_reorder_rejects_a_partial_list(client):
    prog = _create(client)
    a = _add_deadline(client, prog["id"])
    _add_deadline(client, prog["id"], date="2099-02-01")
    r = client.post(f"/api/programs/{prog['id']}/deadlines/reorder", json={"ids": [a["id"]]})
    assert r.status_code == 400


def test_reorder_rejects_unknown_ids(client):
    prog = _create(client)
    a = _add_deadline(client, prog["id"])
    r = client.post(
        f"/api/programs/{prog['id']}/deadlines/reorder", json={"ids": [a["id"], 99999]}
    )
    assert r.status_code == 400


def test_reorder_rejects_a_deadline_from_another_program(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    a_deadline = _add_deadline(client, a["id"])
    b_deadline = _add_deadline(client, b["id"])
    r = client.post(
        f"/api/programs/{a['id']}/deadlines/reorder",
        json={"ids": [b_deadline["id"]]},
    )
    assert r.status_code == 400
    # also rejected the other direction, with a's own deadline missing
    r = client.post(
        f"/api/programs/{a['id']}/deadlines/reorder",
        json={"ids": [a_deadline["id"], b_deadline["id"]]},
    )
    assert r.status_code == 400
