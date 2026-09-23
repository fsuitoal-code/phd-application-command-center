"""The prebuilt frontend that FastAPI serves.

Installed copies never run Node: the React app is built on a dev machine by
``scripts/build_frontend.py`` and the output (``frontend/dist``) is committed, so
an installed copy is one server on :8000. Node is a dev-machine dependency only.

The build stamp records a hash of the frontend *source* at build time. A test
compares it with the current source, so a frontend change pushed without a
rebuild fails the suite instead of shipping a stale UI.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
STAMP = DIST_DIR / "build-stamp.json"

# Everything the build reads. Directories are walked recursively.
_BUILD_INPUTS = (
    "src",
    "public",
    "index.html",
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "tsconfig.json",
)


def _input_files() -> list[Path]:
    files: list[Path] = []
    for name in _BUILD_INPUTS:
        path = FRONTEND_DIR / name
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file())
        elif path.is_file():
            files.append(path)
    return sorted(files, key=lambda p: p.relative_to(FRONTEND_DIR).as_posix())


def source_hash() -> str:
    """sha256 over the frontend's build inputs, stable across OSes."""
    digest = hashlib.sha256()
    for path in _input_files():
        digest.update(path.relative_to(FRONTEND_DIR).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def read_stamp() -> str | None:
    """The source hash the committed build was made from, if there is one."""
    try:
        return json.loads(STAMP.read_text(encoding="utf-8"))["source_hash"]
    except (OSError, ValueError, KeyError):
        return None


def write_stamp() -> None:
    STAMP.write_text(
        json.dumps({"source_hash": source_hash()}) + "\n", encoding="utf-8", newline="\n"
    )
