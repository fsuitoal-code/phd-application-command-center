"""API tests for the per-program application checklist.

Completion is always an explicit user action — these tests pin that nothing
ticks itself. Any step, built-in or custom, can be renamed or deleted per
program; BUILTIN_STEPS only seeds what a new program starts with.
"""

from __future__ import annotations

BUILTIN_LABELS = [
    "Researched requirements",
    "Researched deadlines",
    "Researched faculty",
    "Reach out to faculty",
    "Essays",
    "Polish CV",
    "Submit application",
]


def _create(client, **over):
    payload = {"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"}
    payload.update(over)
    r = client.post("/api/programs", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_new_program_gets_the_builtin_steps_in_order(client):
    prog = _create(client)
    assert [s["label"] for s in prog["steps"]] == BUILTIN_LABELS
    assert all(not s["completed"] for s in prog["steps"])
    assert all(s["completed_at"] is None for s in prog["steps"])
    assert all(not s["is_custom"] for s in prog["steps"])


def test_steps_are_not_inferred_from_other_data(client):
    """Adding a requirement must NOT tick the Requirements step."""
    prog = _create(client)
    client.post(
        f"/api/programs/{prog['id']}/requirements",
        json={"kind": "gre", "value": "Not required"},
    )
    body = client.get(f"/api/programs/{prog['id']}").json()
    requirements_step = next(s for s in body["steps"] if s["key"] == "requirements")
    assert requirements_step["completed"] is False


def test_tick_sets_completed_at_and_untick_clears_it(client):
    prog = _create(client)
    step = prog["steps"][0]

    r = client.patch(
        f"/api/programs/{prog['id']}/steps/{step['id']}", json={"completed": True}
    )
    assert r.status_code == 200, r.text
    assert r.json()["completed"] is True
    assert r.json()["completed_at"] is not None

    r = client.patch(
        f"/api/programs/{prog['id']}/steps/{step['id']}", json={"completed": False}
    )
    assert r.status_code == 200, r.text
    assert r.json()["completed"] is False
    assert r.json()["completed_at"] is None


def test_custom_step_appends_after_the_builtins_and_deletes(client):
    prog = _create(client)
    r = client.post(
        f"/api/programs/{prog['id']}/steps", json={"label": "Writing sample"}
    )
    assert r.status_code == 201, r.text
    custom = r.json()
    assert custom["is_custom"] is True
    assert custom["sort_order"] > prog["steps"][-1]["sort_order"]

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [s["label"] for s in body["steps"]] == BUILTIN_LABELS + ["Writing sample"]

    r = client.delete(f"/api/programs/{prog['id']}/steps/{custom['id']}")
    assert r.status_code == 204, r.text
    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [s["label"] for s in body["steps"]] == BUILTIN_LABELS


def test_builtin_step_can_be_deleted(client):
    """A program's checklist is fully its own now — BUILTIN_STEPS only seeds
    what a new program starts with."""
    prog = _create(client)
    step = prog["steps"][0]
    r = client.delete(f"/api/programs/{prog['id']}/steps/{step['id']}")
    assert r.status_code == 204, r.text
    body = client.get(f"/api/programs/{prog['id']}").json()
    assert len(body["steps"]) == len(BUILTIN_LABELS) - 1
    assert step["id"] not in [s["id"] for s in body["steps"]]


def test_blank_custom_label_rejected(client):
    prog = _create(client)
    r = client.post(f"/api/programs/{prog['id']}/steps", json={"label": "   "})
    assert r.status_code == 400


def test_builtin_step_can_be_renamed(client):
    prog = _create(client)
    step = prog["steps"][0]
    r = client.patch(
        f"/api/programs/{prog['id']}/steps/{step['id']}", json={"label": "Custom name"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["label"] == "Custom name"
    assert r.json()["key"] == step["key"]  # the key is a stable id, not derived from the label


def test_renaming_a_step_leaves_completion_alone(client):
    prog = _create(client)
    step = prog["steps"][0]
    client.patch(f"/api/programs/{prog['id']}/steps/{step['id']}", json={"completed": True})
    r = client.patch(
        f"/api/programs/{prog['id']}/steps/{step['id']}", json={"label": "Renamed"}
    )
    assert r.json()["completed"] is True

    r = client.patch(
        f"/api/programs/{prog['id']}/steps/{step['id']}", json={"completed": False}
    )
    assert r.json()["label"] == "Renamed"


def test_blank_rename_rejected(client):
    prog = _create(client)
    step = prog["steps"][0]
    r = client.patch(
        f"/api/programs/{prog['id']}/steps/{step['id']}", json={"label": "   "}
    )
    assert r.status_code == 400


def test_step_of_another_program_is_404(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    r = client.patch(
        f"/api/programs/{b['id']}/steps/{a['steps'][0]['id']}", json={"completed": True}
    )
    assert r.status_code == 404


def test_reorder_sets_sort_order_by_index(client):
    prog = _create(client)
    ids = [s["id"] for s in prog["steps"]]
    reordered = [ids[2], ids[0], ids[1]] + ids[3:]

    r = client.post(f"/api/programs/{prog['id']}/steps/reorder", json={"ids": reordered})
    assert r.status_code == 200, r.text
    assert [s["id"] for s in r.json()] == reordered
    assert [s["sort_order"] for s in r.json()] == list(range(len(reordered)))

    body = client.get(f"/api/programs/{prog['id']}").json()
    assert [s["id"] for s in body["steps"]] == reordered


def test_reorder_rejects_a_partial_list(client):
    prog = _create(client)
    ids = [s["id"] for s in prog["steps"]]
    r = client.post(f"/api/programs/{prog['id']}/steps/reorder", json={"ids": ids[:-1]})
    assert r.status_code == 400


def test_reorder_rejects_unknown_ids(client):
    prog = _create(client)
    ids = [s["id"] for s in prog["steps"]]
    r = client.post(
        f"/api/programs/{prog['id']}/steps/reorder", json={"ids": ids + [99999]}
    )
    assert r.status_code == 400


def test_reorder_rejects_a_step_from_another_program(client):
    a = _create(client, university="A")
    b = _create(client, university="B")
    a_ids = [s["id"] for s in a["steps"]]
    b_ids = [s["id"] for s in b["steps"]]
    r = client.post(
        f"/api/programs/{a['id']}/steps/reorder",
        json={"ids": [b_ids[0]] + a_ids[1:]},
    )
    assert r.status_code == 400


def test_reorder_includes_custom_steps(client):
    prog = _create(client)
    custom = client.post(
        f"/api/programs/{prog['id']}/steps", json={"label": "Writing sample"}
    ).json()
    ids = [s["id"] for s in prog["steps"]] + [custom["id"]]
    reordered = [custom["id"]] + ids[:-1]

    r = client.post(f"/api/programs/{prog['id']}/steps/reorder", json={"ids": reordered})
    assert r.status_code == 200, r.text
    assert [s["label"] for s in r.json()][0] == "Writing sample"


def test_deleting_a_program_cascades_to_its_steps(client):
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import ProgramStep

    prog = _create(client)
    assert client.delete(f"/api/programs/{prog['id']}").status_code in (200, 204)
    with SessionLocal() as session:
        left = session.scalar(
            select(func.count())
            .select_from(ProgramStep)
            .where(ProgramStep.program_id == prog["id"])
        )
    assert left == 0
