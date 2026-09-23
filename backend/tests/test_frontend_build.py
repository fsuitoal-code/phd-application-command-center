"""The committed frontend build: fresh, and served correctly by FastAPI."""

from __future__ import annotations

from app.frontend import DIST_DIR, read_stamp, source_hash


def test_committed_build_matches_frontend_source():
    assert (DIST_DIR / "index.html").is_file(), (
        "frontend/dist is missing - run 'Run Tests.cmd' (or "
        "'python scripts/build_frontend.py' in backend/) and commit frontend/dist."
    )
    assert read_stamp() == source_hash(), (
        "The frontend source changed since the last build. Run 'Run Tests.cmd' "
        "(or 'python scripts/build_frontend.py' in backend/) and commit the "
        "rebuilt frontend/dist in the same commit."
    )


def _is_app_shell(response) -> bool:
    return response.status_code == 200 and '<div id="root">' in response.text


def test_root_and_client_routes_serve_the_app(client):
    for path in ("/", "/dashboard", "/programs/1"):
        response = client.get(path)
        assert _is_app_shell(response), path
        assert response.headers["cache-control"] == "no-cache"


def test_static_files_are_served(client):
    asset = next((DIST_DIR / "assets").iterdir())
    response = client.get(f"/assets/{asset.name}")
    assert response.status_code == 200
    assert response.content == asset.read_bytes()
    assert client.get("/favicon.ico").status_code == 200


def test_unknown_api_route_stays_a_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_path_traversal_cannot_escape_dist(client):
    response = client.get("/..%2F..%2Fbackend%2Fapp%2Fmain.py")
    assert "FastAPI application entry point" not in response.text
