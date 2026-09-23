#!/bin/bash
# PhD Tracker -- double-click to open (macOS).
#
# Brings the database up to date (snapshotting it first if anything changes),
# starts the app on this Mac account's own local port and opens it in your
# browser. This Terminal window is the app: keep it open while you use PhD
# Tracker, and close it to quit.

cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"
PY="$ROOT/backend/.venv/bin/python"

# One port per Mac account. Every account on a Mac shares 127.0.0.1, so with a
# fixed port one account would find another's running app -- and its data.
# macOS account ids start at 501, giving 8001, 8002, ... (Kept in step with
# the Update launcher.)
UID_NUM="$(id -u)"
if [ "$UID_NUM" -gt 500 ]; then PORT=$((8000 + (UID_NUM - 500) % 1000)); else PORT=8000; fi
URL="http://127.0.0.1:$PORT"

printf '\033]0;PhD Tracker\007'

alert() {
  # The message goes in as an argument, so quotes in it can't break the script.
  osascript -e 'on run argv' \
            -e 'display alert "PhD Tracker" message (item 1 of argv) as critical' \
            -e 'end run' "$1" >/dev/null 2>&1
}

healthy() {
  curl -fsS --max-time 2 "$URL/api/health" >/dev/null 2>&1
}

ours() {
  # True if the PhD Tracker answering at $URL keeps its data in this account's
  # home folder -- that is, it is this account's own app.
  curl -fsS --max-time 2 "$URL/api/health" 2>/dev/null \
    | "$PY" -c 'import json, sys; d = json.load(sys.stdin).get("data_dir", ""); sys.exit(0 if d.startswith(sys.argv[1].rstrip("/") + "/") else 1)' "$HOME" 2>/dev/null
}

echo "PhD Tracker (version $(git rev-parse --short HEAD 2>/dev/null || echo unknown))"
echo

if [ ! -x "$PY" ]; then
  echo "Not set up yet: $PY is missing."
  alert "PhD Tracker isn't set up on this Mac yet. Run the setup steps first."
  exit 1
fi

if healthy; then
  if ours; then
    echo "PhD Tracker is already running. Opening it in your browser."
    open "$URL"
    exit 0
  fi
  echo "Something else is answering at $URL; it isn't this account's PhD Tracker."
  alert "Something else is answering at $URL, so PhD Tracker can't start. Restart the Mac and try again."
  exit 1
fi

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use by another program:"
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  alert "Another program is using port $PORT, so PhD Tracker can't start. Quit that program and try again."
  exit 1
fi

cd "$ROOT/backend" || exit 1

"$PY" -m app.migrate
case $? in
  0) ;;
  2) alert "PhD Tracker can't find its data folder, so it didn't start. Nothing was changed. The Terminal window has the details."
     exit 1 ;;
  3) alert "Your data was last used by a newer version of PhD Tracker. Run Update, then open PhD Tracker again. Nothing was changed."
     exit 1 ;;
  *) alert "PhD Tracker couldn't bring its database up to date, so it didn't start. The Terminal window says what happened."
     exit 1 ;;
esac

echo
echo "Starting PhD Tracker at $URL"
echo "Keep this window open while you use PhD Tracker. Close it to quit."
echo

# Open the browser once the server answers. The server replaces this script's
# process below (exec), so $$ is the server's PID from then on.
SERVER_PID=$$
(
  for _ in $(seq 1 90); do
    if healthy; then
      open "$URL"
      exit 0
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      alert "PhD Tracker stopped while starting. The Terminal window says what happened."
      exit 1
    fi
    sleep 0.5
  done
  alert "PhD Tracker is taking too long to start. The Terminal window may say why."
) &

# No access log: every page makes several requests, and a wall of request
# lines would bury any error worth reading. Errors are still printed here.
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --no-access-log
