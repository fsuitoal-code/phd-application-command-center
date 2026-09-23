"""Build the frontend into frontend/dist and stamp it. Dev machine only.

    python scripts/build_frontend.py        (from backend/, in the venv)

``Run Tests.cmd`` runs this before the suite. Commit the resulting
``frontend/dist`` together with the source change that produced it --
``tests/test_frontend_build.py`` fails if the two drift apart.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.frontend import FRONTEND_DIR, write_stamp  # noqa: E402


def main() -> int:
    npm = shutil.which("npm")
    if npm is None:
        print("npm not found on PATH - building the frontend needs Node (dev machine only).")
        return 1
    result = subprocess.run([npm, "run", "build"], cwd=FRONTEND_DIR)
    if result.returncode != 0:
        print(f"Frontend build failed (npm run build exited {result.returncode}).")
        return result.returncode
    write_stamp()
    print("Frontend built and stamped: frontend/dist")
    return 0


if __name__ == "__main__":
    sys.exit(main())
