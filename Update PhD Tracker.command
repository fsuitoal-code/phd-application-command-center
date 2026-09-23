#!/bin/bash
# PhD Tracker -- double-click to update (macOS).
#
# Downloads the latest version, installs new dependencies if there are any, and
# brings the database up to date. The database is snapshotted before anything
# in it changes, and nothing is touched at all unless the download succeeded.
#
# Everything runs inside main(), which bash reads in full before running it:
# `git pull` may replace this very file, and bash must not read the new copy
# half-way through.

main() {
  cd "$(dirname "$0")" || exit 1
  local root py url old new
  root="$(pwd)"
  py="$root/backend/.venv/bin/python"
  url="http://127.0.0.1:8000"

  printf '\033]0;PhD Tracker - Update\007'

  if [ ! -x "$py" ]; then
    echo "Not set up yet: $py is missing."
    alert critical "PhD Tracker isn't set up on this Mac yet. Run the setup steps first."
    exit 1
  fi

  if curl -fsS --max-time 2 "$url/api/health" >/dev/null 2>&1; then
    alert critical "PhD Tracker is open. Close its Terminal window first, then run Update again."
    exit 1
  fi

  if ! old="$(git rev-parse HEAD)"; then
    alert critical "This PhD Tracker folder isn't a git checkout, so it can't be updated. Nothing was changed."
    exit 1
  fi

  echo "Checking for updates..."
  if ! git pull --ff-only; then
    alert critical "Couldn't download the update. Check your internet connection and try again. Nothing was changed."
    exit 1
  fi
  new="$(git rev-parse HEAD)"

  if [ "$old" = "$new" ]; then
    echo "The code is already the latest version."
  elif ! git diff --quiet "$old" "$new" -- backend/pyproject.toml; then
    echo
    echo "Installing updated components..."
    if ! (cd backend && "$py" -m pip install --quiet --disable-pip-version-check -e .); then
      alert critical "Couldn't install the updated components. Check your internet connection and run Update again. Your data wasn't touched."
      exit 1
    fi
  fi

  echo
  (cd backend && "$py" -m app.migrate)
  case $? in
    0) ;;
    2) alert critical "PhD Tracker can't find its data folder, so the update stopped. Nothing in your data was changed. The Terminal window has the details."
       exit 1 ;;
    *) alert critical "The update was downloaded, but the database couldn't be brought up to date. The Terminal window says what happened."
       exit 1 ;;
  esac

  local version
  version="$(git rev-parse --short HEAD)"
  echo
  echo "PhD Tracker is up to date (version $version)."
  alert informational "PhD Tracker is up to date (version $version). You can open it now."
  exit 0
}

alert() {
  # alert <critical|informational> <message>. The message goes in as an
  # argument, so quotes in it can't break the script.
  osascript -e 'on run argv' \
            -e "display alert \"PhD Tracker\" message (item 1 of argv) as $1" \
            -e 'end run' "$2" >/dev/null 2>&1
}

# One line, so bash has parsed the exit before main runs.
main "$@"; exit $?
