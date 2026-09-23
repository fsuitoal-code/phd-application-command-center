"""API tests for editing, deleting, and manually reordering a program's requirements.

`kind` is free text, not a fixed enum — the UI offers common cases as
suggestions, but a program's own requirement can be labelled anything.

Every new program is also seeded with the six built-in requirement kinds
(see test_requirement_seeding.py) — unrelated to what these CRUD/reorder
tests exercise, so `_create` strips them to start from a clean slate.
"""

from __future__ import annotations


def _create(client, **over):
    payload = {"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"}
    payload.update(over)
    r = client.post("/api/programs", json=payload)
    assert r.status_code == 201, r.text
    prog = r.json()
    for req in prog["requirements"]:
        client.delete(f"/api/programs/{prog['id']}/requirements/{req['id']}")
    prog["requirements"] = []
    return prog


def _add_requirement(client, pid, **over):
    payload = {"kind": "gre", "value": None}
    payload.update(over)
    r = client.post(f"/api/programs/{pid}/requirements", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_new_requirements_are_appended_in_sort_order(client):
    prog = _create(client)
    a = _add_requirement(client, prog["id"], kind="gre")
    b = _add_requirement(client, prog["id"], kind="toefl")
    assert b["sort_order"] > a["sort_order"]

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [r["id"] for r in body["requirements"]] == [a["id"], b["id"]]


def test_edit_updates_only_provided_fields(client):
    prog = _create(client)
    req = _add_requirement(client, prog["id"], kind="gre", value="orig")

    r = client.patch(
        f"/api/programs/{prog['id']}/requirements/{req['id']}", json={"value": "not required"}
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["value"] == "not required"
    assert updated["kind"] == "gre"


def test_editing_value_auto_confirms(client):
    prog = _create(client)
    # A plain add defaults to already-confirmed (see RequirementCreate); this
    # test is about the researched -> confirmed transition, so start there.
    req = _add_requirement(
        client, prog["id"], kind="gre", value="orig",
        source="researched", needs_human_verification=True,
    )
    assert req["source"] == "researched"
    assert req["needs_human_verification"] is True

    r = client.patch(
        f"/api/programs/{prog['id']}/requirements/{req['id']}", json={"value": "not required"}
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["source"] == "confirmed_by_program"
    assert updated["needs_human_verification"] is False


def test_editing_kind_alone_also_auto_confirms(client):
    prog = _create(client)
    req = _add_requirement(client, prog["id"], kind="gre")

    r = client.patch(
        f"/api/programs/{prog['id']}/requirements/{req['id']}", json={"kind": "toefl"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "confirmed_by_program"


def test_edit_with_explicit_source_is_not_overridden(client):
    prog = _create(client)
    req = _add_requirement(client, prog["id"], kind="gre")

    r = client.patch(
        f"/api/programs/{prog['id']}/requirements/{req['id']}",
        json={"value": "not required", "source": "researched"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "researched"


def test_kind_accepts_arbitrary_free_text(client):
    prog = _create(client)
    req = _add_requirement(client, prog["id"], kind="writing sample")
    assert req["kind"] == "writing sample"

    r = client.patch(
        f"/api/programs/{prog['id']}/requirements/{req['id']}",
        json={"kind": "portfolio"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "portfolio"


def test_add_blank_kind_falls_back_to_other(client):
    prog = _create(client)
    req = _add_requirement(client, prog["id"], kind="   ")
    assert req["kind"] == "other"


def test_edit_rejects_a_blank_kind(client):
    prog = _create(client)
    req = _add_requirement(client, prog["id"])
    r = client.patch(
        f"/api/programs/{prog['id']}/requirements/{req['id']}", json={"kind": "   "}
    )
    assert r.status_code == 400


def test_edit_can_explicitly_clear_value(client):
    prog = _create(client)
    req = _add_requirement(client, prog["id"], value="orig")

    r = client.patch(
        f"/api/programs/{prog['id']}/requirements/{req['id']}", json={"value": None}
    )
    assert r.status_code == 200, r.text
    assert r.json()["value"] is None


def test_requirement_of_another_program_is_404(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    req = _add_requirement(client, a["id"])
    r = client.patch(
        f"/api/programs/{b['id']}/requirements/{req['id']}", json={"value": "x"}
    )
    assert r.status_code == 404


def test_delete_removes_the_requirement(client):
    prog = _create(client)
    req = _add_requirement(client, prog["id"])
    r = client.delete(f"/api/programs/{prog['id']}/requirements/{req['id']}")
    assert r.status_code == 204, r.text

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert body["requirements"] == []


def test_reorder_sets_sort_order_by_index(client):
    prog = _create(client)
    a = _add_requirement(client, prog["id"], kind="gre")
    b = _add_requirement(client, prog["id"], kind="toefl")
    c = _add_requirement(client, prog["id"], kind="app_fee")
    reordered = [c["id"], a["id"], b["id"]]

    r = client.post(
        f"/api/programs/{prog['id']}/requirements/reorder", json={"ids": reordered}
    )
    assert r.status_code == 200, r.text
    assert [req["id"] for req in r.json()] == reordered
    assert [req["sort_order"] for req in r.json()] == [0, 1, 2]

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [req["id"] for req in body["requirements"]] == reordered


def test_reorder_rejects_a_partial_list(client):
    prog = _create(client)
    a = _add_requirement(client, prog["id"])
    _add_requirement(client, prog["id"], kind="toefl")
    r = client.post(
        f"/api/programs/{prog['id']}/requirements/reorder", json={"ids": [a["id"]]}
    )
    assert r.status_code == 400


def test_reorder_rejects_unknown_ids(client):
    prog = _create(client)
    a = _add_requirement(client, prog["id"])
    r = client.post(
        f"/api/programs/{prog['id']}/requirements/reorder",
        json={"ids": [a["id"], 99999]},
    )
    assert r.status_code == 400


def test_reorder_rejects_a_requirement_from_another_program(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    a_req = _add_requirement(client, a["id"])
    b_req = _add_requirement(client, b["id"])
    r = client.post(
        f"/api/programs/{a['id']}/requirements/reorder",
        json={"ids": [b_req["id"]]},
    )
    assert r.status_code == 400
    r = client.post(
        f"/api/programs/{a['id']}/requirements/reorder",
        json={"ids": [a_req["id"], b_req["id"]]},
    )
    assert r.status_code == 400
