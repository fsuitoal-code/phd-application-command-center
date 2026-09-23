# PhD Application Command Center

A local-first tracker for PhD applications: the programs you're applying to,
their deadlines and requirements, the faculty you'd like to work with, and your
own documents and notes. Claude can do the first pass of research on a program
or a faculty member, with every fact cited back to its source.

> **A personal project.** I built this for my own application season and share
> the code as-is. It isn't a supported product: there are no releases, no
> support and no roadmap commitments, and things may change or break without
> notice.

## What it does

- **Programs.** One row per program (university, department, degree), in the
  order you drag them into, with a checklist you define and set yourself.
  Nothing marks a step done for you.
- **Program page**, in four tabs:
  - *Overview*: deadlines, requirements (GRE, TOEFL, fees, letters, essays) and
    researched facts.
  - *Faculty*: a short list of research faculty you're interested in, each with
    a cited profile and your own notes.
  - *My Docs*: the CV, statement of purpose and other files tailored to that
    program. Stored only, never read by Claude.
  - *My Notes*: a free-form scratchpad of notes, links, files and reminders.
- **Dashboard.** Every deadline and reminder in date order, a "needs
  attention" list, a checklist grid and a side-by-side comparison of programs.
- **Research with Claude** (optional):
  - *Program research* reads only the program's own official website.
  - *Faculty profiles* can search the wider web, but never Google Scholar.
  - *Suggest more faculty* proposes additional people from the department.

  Every researched item quotes its source and is marked as needing your
  verification. When a program confirms something itself, you can mark it
  confirmed.

## Privacy

Everything stays on your machine. The database, your uploaded documents and
your notes live in a local data folder outside the code:

| OS      | Data folder                                   |
|---------|-----------------------------------------------|
| macOS   | `~/Library/Application Support/PhDTracker/`   |
| Windows | `%LOCALAPPDATA%\PhDTracker\`                  |
| Linux   | `$XDG_DATA_HOME/PhDTracker/` (or `~/.local/share/PhDTracker/`) |

Set `PHDTRACKER_DATA_DIR` to use a different folder. Updating the code never
touches this folder. Back it up like any file you'd hate to lose.

The app makes no network calls of its own apart from the Claude research you
start yourself. That research runs through the Claude Agent SDK on your own
Claude account.

The rules the code is built to are in [docs/principles.md](docs/principles.md).

## Requirements

- Python 3.12 or newer
- Git
- For the research features: [Claude Code](https://code.claude.com), signed in
  to your own Claude account. Research runs on your account and counts
  towards your plan's usage limits. Everything else works without it.

## Setup

```bash
git clone https://github.com/fsuitoal-code/phd-application-command-center.git
cd phd-application-command-center/backend
python3 -m venv .venv        # on Windows: python -m venv .venv
```

Then, on **macOS / Linux**:

```bash
.venv/bin/python -m pip install -e .
.venv/bin/python -m app.init_data_dir     # creates the data folder, once
.venv/bin/python -m app.migrate           # creates the database
```

On **Windows**:

```bash
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m app.init_data_dir
.venv\Scripts\python -m app.migrate
```

The app never creates a data folder by itself. If it can't find a database
where it expects one, it stops with an error naming the path, instead of
opening an empty app that looks as if your data vanished. `init_data_dir` is
the one deliberate way to create one.

To use the research features, sign in once with `claude /login`. You can then
check the connection with `python scripts/verify_sdk.py`. That makes one
small request on your account.

## Running

On **macOS**, double-click **`Open PhD Tracker.command`** in the project
folder. It brings the database up to date, starts the app and opens it in your
browser. The Terminal window it opens *is* the app: keep it open while you use
PhD Tracker, and close it to quit.

Otherwise, from `backend/`:

```bash
.venv/bin/python -m uvicorn app.main:app --port 8000      # macOS / Linux
.venv\Scripts\python -m uvicorn app.main:app --port 8000  # Windows
```

Then open <http://127.0.0.1:8000>. The backend serves the prebuilt web app, so
Node isn't needed to run it.

## Updating

On **macOS**, close PhD Tracker and double-click **`Update PhD Tracker.command`**.

Otherwise:

```bash
git pull
cd backend
.venv/bin/python -m pip install -e .
.venv/bin/python -m app.migrate
```

Migrations only move forward. When the database needs changing, `app.migrate`
first writes a consistent snapshot of it to the `backups/` folder inside your
data folder. If that snapshot fails, nothing is changed. When the database is
already up to date, it touches nothing.

## Development

The stack is FastAPI, SQLAlchemy, Alembic and SQLite on the backend, and
React 19, TypeScript, Tailwind 4 and Vite on the frontend. Node is only needed
to change the frontend:

```bash
cd frontend && npm install && npm run dev     # http://localhost:5173, proxies /api to :8000
```

The built frontend is committed in `frontend/dist`. After changing the
frontend, rebuild it with `python scripts/build_frontend.py` (from `backend/`)
and commit the result together with your change.
`backend/tests/test_frontend_build.py` fails if the committed build no longer
matches the source. On Windows, `Run Tests.cmd` rebuilds and then runs the test
suite, and `Run PhD Tracker.cmd` starts both dev servers.

Tests: `cd backend && .venv/bin/python -m pytest`.

## Notes

- Not affiliated with, or endorsed by, Anthropic or any university.
- University and faculty names appear as plain text only. The app ships no
  third-party logos or images.
- Research output is a starting point, not an authority. Check everything
  against the program's own pages before relying on it.
- No licence is granted. You're welcome to read the code, but all rights are
  reserved.
