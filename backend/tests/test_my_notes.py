"""API tests for a program's My Notes: text, link, file, due date; reorder."""

from __future__ import annotations

from pathlib import Path


def _program(client, **over):
    payload = {"university": "UW-Madison", "department": "Computer Science", "degree": "PhD"}
    payload.update(over)
    r = client.post("/api/programs", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _add(client, pid, text="Portal login is my school email", files=None, **fields):
    r = client.post(f"/api/programs/{pid}/my-notes", data={"text": text, **fields}, files=files)
    assert r.status_code == 201, r.text
    return r.json()


def _my_notes(client, pid):
    return client.get(f"/api/programs/{pid}").json()["my_notes"]


def _stored_files():
    from app.paths import notes_dir

    return list(notes_dir().iterdir())


def test_new_program_has_no_my_notes(client):
    assert _my_notes(client, _program(client)["id"]) == []


def test_note_shape(client):
    n = _add(client, _program(client)["id"])
    assert set(n.keys()) == {
        "id", "program_id", "text", "link_url", "due_date", "file_name", "sort_order"
    }
    assert (n["link_url"], n["due_date"], n["file_name"]) == (None, None, None)


def test_notes_append_in_order_and_keep_line_breaks(client):
    pid = _program(client)["id"]
    a = _add(client, pid, "First")
    b = _add(client, pid, "  Line one\nLine two  ")
    assert b["sort_order"] > a["sort_order"]
    assert b["text"] == "Line one\nLine two"
    assert [n["id"] for n in _my_notes(client, pid)] == [a["id"], b["id"]]


def test_note_with_link_and_date_only(client):
    pid = _program(client)["id"]
    n = _add(client, pid, "", link_url=" https://example.edu/apply ", due_date="2026-12-01")
    assert n["text"] == ""
    assert n["link_url"] == "https://example.edu/apply"
    assert n["due_date"] == "2026-12-01"


def test_add_rejects_an_empty_note(client):
    pid = _program(client)["id"]
    r = client.post(f"/api/programs/{pid}/my-notes", data={"text": "  ", "link_url": ""})
    assert r.status_code == 400


def test_add_rejects_non_http_link_and_bad_date(client):
    pid = _program(client)["id"]
    url = f"/api/programs/{pid}/my-notes"
    assert client.post(url, data={"link_url": "javascript:alert(1)"}).status_code == 400
    assert client.post(url, data={"link_url": "example.edu"}).status_code == 400
    assert client.post(url, data={"due_date": "next week"}).status_code == 400


def test_add_to_missing_program_is_404(client):
    assert client.post("/api/programs/9999/my-notes", data={"text": "x"}).status_code == 404


def test_file_only_note_is_stored_and_served(client):
    pid = _program(client)["id"]
    n = _add(client, pid, "", files={"file": ("fee waiver.pdf", b"%PDF-1.4 hi", "application/pdf")})
    assert n["file_name"] == "fee waiver.pdf"

    r = client.get(f"/api/programs/{pid}/my-notes/{n['id']}/file")
    assert r.status_code == 200
    assert r.content == b"%PDF-1.4 hi"
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")


def test_replacing_a_file_removes_the_old_one(client):
    pid = _program(client)["id"]
    n = _add(client, pid, "cv", files={"file": ("a.txt", b"old", "text/plain")})
    before = set(_stored_files())
    r = client.put(
        f"/api/programs/{pid}/my-notes/{n['id']}/file",
        files={"file": ("b.txt", b"new", "text/plain")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["file_name"] == "b.txt"
    after = set(_stored_files())
    assert len(after) == len(before)
    assert client.get(f"/api/programs/{pid}/my-notes/{n['id']}/file").content == b"new"


def test_removing_the_file(client):
    pid = _program(client)["id"]
    n = _add(client, pid, "keep me", files={"file": ("a.txt", b"x", "text/plain")})
    r = client.delete(f"/api/programs/{pid}/my-notes/{n['id']}/file")
    assert r.status_code == 200, r.text
    assert r.json()["file_name"] is None
    assert client.get(f"/api/programs/{pid}/my-notes/{n['id']}/file").status_code == 404


def test_cannot_remove_the_only_thing_a_note_holds(client):
    pid = _program(client)["id"]
    n = _add(client, pid, "", files={"file": ("a.txt", b"x", "text/plain")})
    assert client.delete(f"/api/programs/{pid}/my-notes/{n['id']}/file").status_code == 400


def test_deleting_note_or_program_deletes_its_file(client):
    pid = _program(client)["id"]
    before = set(_stored_files())
    n = _add(client, pid, "", files={"file": ("a.txt", b"x", "text/plain")})
    _add(client, pid, "", files={"file": ("b.txt", b"y", "text/plain")})
    assert len(set(_stored_files()) - before) == 2

    assert client.delete(f"/api/programs/{pid}/my-notes/{n['id']}").status_code == 204
    assert len(set(_stored_files()) - before) == 1
    assert client.delete(f"/api/programs/{pid}").status_code == 204
    assert set(_stored_files()) == before


def test_patch_updates_and_clears_fields(client):
    pid = _program(client)["id"]
    n = _add(client, pid, "orig", link_url="https://a.edu", due_date="2026-11-01")
    url = f"/api/programs/{pid}/my-notes/{n['id']}"

    r = client.patch(url, json={"text": "fixed"})
    assert r.status_code == 200, r.text
    assert (r.json()["text"], r.json()["link_url"]) == ("fixed", "https://a.edu")

    r = client.patch(url, json={"link_url": None, "due_date": None})
    assert (r.json()["link_url"], r.json()["due_date"]) == (None, None)

    assert client.patch(url, json={"text": " "}).status_code == 400
    assert client.patch(url, json={"link_url": "ftp://x"}).status_code == 400


def test_note_of_another_program_is_404(client):
    a = _program(client, university="A")["id"]
    b = _program(client, university="B")["id"]
    n = _add(client, a)
    assert client.patch(f"/api/programs/{b}/my-notes/{n['id']}", json={"text": "x"}).status_code == 404
    assert client.delete(f"/api/programs/{b}/my-notes/{n['id']}").status_code == 404
    assert client.get(f"/api/programs/{b}/my-notes/{n['id']}/file").status_code == 404


def test_file_outside_notes_dir_is_not_served(client):
    from app.db import SessionLocal
    from app.models import MyNote

    pid = _program(client)["id"]
    n = _add(client, pid, "x", files={"file": ("a.txt", b"x", "text/plain")})
    with SessionLocal() as session:
        row = session.get(MyNote, n["id"])
        row.file_path = str(Path(__file__).resolve())
        session.commit()
    assert client.get(f"/api/programs/{pid}/my-notes/{n['id']}/file").status_code == 404


def test_reorder_sets_sort_order_by_index(client):
    pid = _program(client)["id"]
    a, b, c = (_add(client, pid, t) for t in "ABC")
    reordered = [c["id"], a["id"], b["id"]]
    r = client.post(f"/api/programs/{pid}/my-notes/reorder", json={"ids": reordered})
    assert r.status_code == 200, r.text
    assert [n["id"] for n in r.json()] == reordered
    assert [n["sort_order"] for n in r.json()] == [0, 1, 2]
    assert [n["id"] for n in _my_notes(client, pid)] == reordered


def test_reorder_rejects_partial_or_foreign_ids(client):
    a = _program(client, university="A")["id"]
    b = _program(client, university="B")["id"]
    n1 = _add(client, a)
    _add(client, a, "second")
    foreign = _add(client, b)
    assert client.post(f"/api/programs/{a}/my-notes/reorder", json={"ids": [n1["id"]]}).status_code == 400
    assert (
        client.post(f"/api/programs/{a}/my-notes/reorder", json={"ids": [foreign["id"]]}).status_code
        == 400
    )
