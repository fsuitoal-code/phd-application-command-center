"""API tests for program intake and tracking."""

from __future__ import annotations


def _create(client, **over):
    payload = {"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"}
    payload.update(over)
    r = client.post("/api/programs", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _application_deadline_id(client, pid):
    deadlines = client.get(f"/api/programs/{pid}").json()["deadlines"]
    return next(d["id"] for d in deadlines if d["type"] == "application")


def test_list_uses_the_manual_order_not_the_deadline(client):
    """The list is the user's order; a sooner deadline does not jump the queue.

    Urgency is still surfaced per row and still drives the dashboard.
    """
    a = _create(client, university="A")
    b = _create(client, university="B")
    # Every program is seeded with a blank Application deadline; filling in
    # its date is a PATCH, same as the detail page does -- not a new POST.
    client.patch(
        f"/api/programs/{a['id']}/deadlines/{_application_deadline_id(client, a['id'])}",
        json={"date": "2099-12-01"},
    )
    client.patch(
        f"/api/programs/{b['id']}/deadlines/{_application_deadline_id(client, b['id'])}",
        json={"date": "2099-01-01"},
    )

    rows = client.get("/api/programs").json()
    # A was added first, so it stays first despite B's sooner deadline.
    assert [row["university"] for row in rows] == ["A", "B"]
    b_row = next(r for r in rows if r["university"] == "B")
    assert b_row["application_deadline"] == "2099-01-01"
    assert b_row["urgency"] is not None


def test_manually_added_requirement_defaults_to_confirmed(client):
    # Typed in by hand through this endpoint -- there is nothing to verify,
    # unlike a fact an actual research pass writes (source=researched).
    prog = _create(client)
    r = client.post(
        f"/api/programs/{prog['id']}/requirements",
        json={"kind": "gre", "value": "GRE not required"},
    )
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["source"] == "confirmed_by_program"
    assert req["needs_human_verification"] is False


def test_delete_cascades(client):
    prog = _create(client)
    pid = prog["id"]
    client.post(f"/api/programs/{pid}/faculty", json={"name": "Prof X"})
    client.post(f"/api/programs/{pid}/deadlines", json={"date": "2099-01-01"})
    assert client.delete(f"/api/programs/{pid}").status_code == 204
    assert client.get(f"/api/programs/{pid}").status_code == 404


def test_add_faculty_and_detail_roundtrip(client):
    prog = _create(client)
    pid = prog["id"]
    client.post(
        f"/api/programs/{pid}/faculty",
        json={"name": "Prof X", "research_areas": "ML", "contacted": False},
    )
    detail = client.get(f"/api/programs/{pid}").json()
    assert len(detail["faculty"]) == 1
    assert detail["faculty"][0]["name"] == "Prof X"


def test_404_on_missing_program(client):
    assert client.get("/api/programs/99999").status_code == 404


def test_research_model_is_null_for_a_hand_added_program(client):
    # The column answers "what produced these facts", not "what would a pass
    # use now" -- so a program typed in by hand must not claim a model.
    r = client.post("/api/programs", json={"university": "Typed By Hand"})
    assert r.status_code == 201
    assert r.json()["research_model"] is None

    detail = client.get(f"/api/programs/{r.json()['id']}").json()
    assert detail["research_model"] is None
