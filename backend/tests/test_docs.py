"""My Docs: per-program doc-type registry (builtin seeding, add/rename/delete)
and file upload/open/delete under a type. Pure file storage — nothing here is
ever read by Claude. Each program's documents are independent of every
other's."""

from __future__ import annotations

import io
from pathlib import Path


def _create_program(client, **over):
    payload = {"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"}
    payload.update(over)
    r = client.post("/api/programs", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, program_id: int, doc_type_id: int, name: str, data: bytes):
    return client.post(
        f"/api/programs/{program_id}/docs/{doc_type_id}/files",
        files={"file": (name, io.BytesIO(data), "application/octet-stream")},
    )


# ── Doc types ────────────────────────────────────────────────────────────
def test_builtin_types_are_seeded_on_first_list(client):
    prog = _create_program(client)
    r = client.get(f"/api/programs/{prog['id']}/docs")
    assert r.status_code == 200
    rows = r.json()
    keys = [d["key"] for d in rows]
    assert keys == ["cv", "sop"]
    assert [d["title"] for d in rows] == ["CV", "Statement of Purpose"]
    assert all(d["program_id"] == prog["id"] for d in rows)
    assert all(d["is_custom"] is False for d in rows)
    assert all(d["files"] == [] for d in rows)


def test_seeding_is_idempotent(client):
    prog = _create_program(client)
    client.get(f"/api/programs/{prog['id']}/docs")
    r = client.get(f"/api/programs/{prog['id']}/docs")
    assert len(r.json()) == 2


def test_list_unknown_program_404s(client):
    assert client.get("/api/programs/999/docs").status_code == 404


def test_doc_types_are_independent_per_program(client):
    """A CV/SOP tailored to one program must not show up on another's."""
    a = _create_program(client, university="A")
    b = _create_program(client, university="B")

    types_a = client.get(f"/api/programs/{a['id']}/docs").json()
    cv_a = next(d for d in types_a if d["key"] == "cv")
    _upload(client, a["id"], cv_a["id"], "a-cv.txt", b"a's cv")

    client.post(f"/api/programs/{a['id']}/docs", json={"title": "Writing Sample"})

    types_b = client.get(f"/api/programs/{b['id']}/docs").json()
    assert [d["title"] for d in types_b] == ["CV", "Statement of Purpose"]
    assert all(d["files"] == [] for d in types_b)


def test_add_custom_doc_type(client):
    prog = _create_program(client)
    client.get(f"/api/programs/{prog['id']}/docs")  # seed builtins first
    r = client.post(f"/api/programs/{prog['id']}/docs", json={"title": "Writing Sample"})
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["title"] == "Writing Sample"
    assert row["is_custom"] is True
    assert row["program_id"] == prog["id"]

    all_types = client.get(f"/api/programs/{prog['id']}/docs").json()
    assert [d["title"] for d in all_types] == ["CV", "Statement of Purpose", "Writing Sample"]


def test_add_doc_type_to_unknown_program_404s(client):
    assert client.post("/api/programs/999/docs", json={"title": "x"}).status_code == 404


def test_rename_doc_type_title_only(client):
    """Built-in types may be renamed too — same rule as program_steps."""
    prog = _create_program(client)
    cv = client.get(f"/api/programs/{prog['id']}/docs").json()[0]
    r = client.patch(f"/api/docs/{cv['id']}", json={"title": "My CV"})
    assert r.status_code == 200
    assert r.json()["title"] == "My CV"
    assert r.json()["key"] == "cv"  # the stable key never changes


def test_rename_blank_title_rejected(client):
    prog = _create_program(client)
    cv = client.get(f"/api/programs/{prog['id']}/docs").json()[0]
    r = client.patch(f"/api/docs/{cv['id']}", json={"title": "   "})
    assert r.status_code == 422


def test_rename_unknown_doc_type_404s(client):
    assert client.patch("/api/docs/999", json={"title": "x"}).status_code == 404


def test_delete_doc_type(client):
    """Built-in types are deletable too — nothing here is protected."""
    prog = _create_program(client)
    types = client.get(f"/api/programs/{prog['id']}/docs").json()
    sop_id = next(d["id"] for d in types if d["key"] == "sop")
    assert client.delete(f"/api/docs/{sop_id}").status_code == 204
    remaining = client.get(f"/api/programs/{prog['id']}/docs").json()
    assert [d["key"] for d in remaining] == ["cv"]


def test_delete_doc_type_removes_its_files(client):
    from app.paths import docs_dir

    prog = _create_program(client)
    cv = client.get(f"/api/programs/{prog['id']}/docs").json()[0]
    f = _upload(client, prog["id"], cv["id"], "resume.txt", b"my cv").json()
    stored = Path(docs_dir()) / f"{f['id']}-resume.txt"
    assert stored.exists()

    assert client.delete(f"/api/docs/{cv['id']}").status_code == 204
    assert not stored.exists()


def test_delete_unknown_doc_type_404s(client):
    assert client.delete("/api/docs/999").status_code == 404


# ── Files ────────────────────────────────────────────────────────────────
def test_upload_lists_newest_first(client):
    prog = _create_program(client)
    cv = client.get(f"/api/programs/{prog['id']}/docs").json()[0]
    first = _upload(client, prog["id"], cv["id"], "old.txt", b"old").json()
    second = _upload(client, prog["id"], cv["id"], "new.txt", b"new").json()

    files = client.get(f"/api/programs/{prog['id']}/docs").json()[0]["files"]
    assert [f["id"] for f in files] == [second["id"], first["id"]]


def test_upload_to_unknown_doc_type_404s(client):
    prog = _create_program(client)
    r = _upload(client, prog["id"], 999, "x.txt", b"x")
    assert r.status_code == 404


def test_upload_to_another_programs_doc_type_404s(client):
    a = _create_program(client, university="A")
    b = _create_program(client, university="B")
    cv_a = client.get(f"/api/programs/{a['id']}/docs").json()[0]

    r = _upload(client, b["id"], cv_a["id"], "x.txt", b"x")
    assert r.status_code == 404


def test_open_uploaded_file_serves_it(client):
    prog = _create_program(client)
    cv = client.get(f"/api/programs/{prog['id']}/docs").json()[0]
    data = b"# CV\n\n- Built a telescope pipeline"
    row = _upload(client, prog["id"], cv["id"], "cv.md", data).json()

    r = client.get(f"/api/docs/files/{row['id']}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.headers["content-disposition"].startswith("inline")
    assert r.content == data


def test_open_missing_file_tells_the_user_to_re_upload(client):
    prog = _create_program(client)
    cv = client.get(f"/api/programs/{prog['id']}/docs").json()[0]
    row = _upload(client, prog["id"], cv["id"], "gone.txt", b"about to vanish").json()

    from app.paths import docs_dir

    (Path(docs_dir()) / f"{row['id']}-gone.txt").unlink()

    r = client.get(f"/api/docs/files/{row['id']}")
    assert r.status_code == 404
    assert "re-upload" in r.json()["detail"]


def test_open_refuses_a_path_outside_the_docs_directory(client):
    """A hand-edited database must not turn this into a file-read primitive."""
    from app.db import SessionLocal
    from app.models import DocFile

    prog = _create_program(client)
    cv = client.get(f"/api/programs/{prog['id']}/docs").json()[0]
    row = _upload(client, prog["id"], cv["id"], "ok.txt", b"fine").json()
    with SessionLocal() as session:
        f = session.get(DocFile, row["id"])
        f.stored_path = str(Path(__file__).resolve())  # outside docs_dir()
        session.commit()

    r = client.get(f"/api/docs/files/{row['id']}")
    assert r.status_code == 404
    assert "not readable" in r.json()["detail"]


def test_open_unknown_file_404s(client):
    assert client.get("/api/docs/files/999").status_code == 404


def test_delete_file(client):
    from app.paths import docs_dir

    prog = _create_program(client)
    cv = client.get(f"/api/programs/{prog['id']}/docs").json()[0]
    row = _upload(client, prog["id"], cv["id"], "a.txt", b"a").json()
    stored = Path(docs_dir()) / f"{row['id']}-a.txt"
    assert stored.exists()

    assert client.delete(f"/api/docs/files/{row['id']}").status_code == 204
    assert not stored.exists()
    assert client.get(f"/api/programs/{prog['id']}/docs").json()[0]["files"] == []


def test_delete_unknown_file_404s(client):
    assert client.delete("/api/docs/files/999").status_code == 404


def test_deleting_program_removes_its_doc_types(client):
    prog = _create_program(client)
    client.get(f"/api/programs/{prog['id']}/docs")  # seed
    assert client.delete(f"/api/programs/{prog['id']}").status_code == 204
    # The doc types went with the program (CASCADE) — renaming one 404s now.
    assert client.get(f"/api/programs/{prog['id']}/docs").status_code == 404
