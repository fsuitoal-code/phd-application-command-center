"""FastAPI application entry point.

Wires the API routers, CORS for the Vite dev server, and (when a build is
present) the prebuilt frontend.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import ClaudeTask, settings
from app.frontend import DIST_DIR
from app.paths import data_dir, database_path
from app.routers import (
    dashboard,
    docs,
    faculty,
    my_notes,
    profile,
    programs,
)

app = FastAPI(title="PhD Application Command Center", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(programs.router)
app.include_router(profile.router)
app.include_router(faculty.router)
app.include_router(docs.router)
app.include_router(docs.program_router)
app.include_router(my_notes.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health() -> dict:
    """Liveness + environment probe.

    Reports where this machine's data lives and how tasks map to models, so a
    new installation can confirm the app-data dir resolved correctly without
    opening a shell.
    """
    return {
        "status": "ok",
        "data_dir": str(data_dir()),
        "database": str(database_path()),
        "models": {task.value: settings.model_for(task) for task in ClaudeTask},
    }


# ── The prebuilt frontend ──────────────────────────────────────────────────
# Registered last, so every API route above wins. In development the Vite
# server on :5173 serves the UI instead and this block is simply unused; with no
# build present (e.g. a fresh clone before the first build) it isn't mounted.
if (DIST_DIR / "index.html").is_file():
    _DIST = DIST_DIR.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        # An unknown API route must stay a JSON 404, not turn into the app page.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        if path:
            candidate = (_DIST / path).resolve()
            # Containment check: a crafted path must not read outside dist/.
            if candidate.is_relative_to(_DIST) and candidate.is_file():
                return FileResponse(candidate)
        # Client-side routes (/programs/3, /dashboard) all load the app shell.
        # no-cache so a freshly updated build is picked up on the next load.
        return FileResponse(_DIST / "index.html", headers={"Cache-Control": "no-cache"})
