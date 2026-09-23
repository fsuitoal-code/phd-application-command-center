#!/bin/bash
# PhD Tracker -- macOS setup.
#
# Run it by pasting this one line into Terminal (it downloads and runs this file):
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/fsuitoal-code/phd-application-command-center/main/setup-mac.sh)"
#
# Python 3.12 or newer must already be installed (python.org). The setup then
# installs Apple's command line tools if they're missing (git needs them),
# downloads the app to ~/PhDTracker, sets up its Python environment, creates
# the data folder and database, and signs you in to Claude.
#
# Safe to run again: every step checks before it acts. Your data is only ever
# touched to bring the database up to date, and that takes a backup first.

REPO_URL="https://github.com/fsuitoal-code/phd-application-command-center.git"
REPO_PATH="fsuitoal-code/phd-application-command-center"
APP_DIR="$HOME/PhDTracker"
DATA_DIR="$HOME/Library/Application Support/PhDTracker"
LOG_DIR="$HOME/Library/Logs/PhDTracker"

say()  { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
ok()   { printf '    %s\n' "$*"; }
warn() { printf '    WARNING: %s\n' "$*"; }

fail() {
  printf '\nSetup stopped: %s\n' "$*"
  printf '\nIf you are stuck, send this file to whoever is helping you:\n  %s\n' "$LOG"
  exit 1
}

ask() {
  # ask <prompt> -- reads the answer from the keyboard into $ANSWER.
  ANSWER=""
  read -r -p "$1" ANSWER </dev/tty || ANSWER=""
}

py_version_ok() {
  # Prints "MAJOR MINOR" if $1 is a working Python 3.12 or newer; fails otherwise.
  "$1" -c 'import sys; v = sys.version_info; print(v[0], v[1]) if v >= (3, 12) else sys.exit(1)' 2>/dev/null
}

find_python() {
  # Prints the newest usable Python (3.12+) found on this Mac; fails if none.
  local best="" best_minor=-1 name p ver minor
  local candidates=""
  for name in python3.16 python3.15 python3.14 python3.13 python3.12 python3; do
    p="$(command -v "$name" 2>/dev/null)" && candidates="$candidates $p"
  done
  for p in $candidates \
           /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 \
           /opt/homebrew/bin/python3.1[2-9] /opt/homebrew/bin/python3 \
           /usr/local/bin/python3.1[2-9] /usr/local/bin/python3; do
    [ -x "$p" ] || continue
    ver="$(py_version_ok "$p")" || continue
    minor="${ver#* }"
    if [ "$minor" -gt "$best_minor" ]; then
      best="$p"
      best_minor="$minor"
    fi
  done
  [ -n "$best" ] && printf '%s\n' "$best"
}

main() {
  [ -n "$HOME" ] || { echo "HOME is not set."; exit 1; }
  [ "$(id -u)" -ne 0 ] || { echo "Run this setup as yourself, without sudo."; exit 1; }
  [ "$(uname -s)" = "Darwin" ] || { echo "This setup is for macOS."; exit 1; }

  # Keep the real terminal on fds 3 and 4 for the interactive sign-in, and copy
  # everything else to a log file that can be sent to whoever is helping.
  mkdir -p "$LOG_DIR"
  LOG="$LOG_DIR/setup-$(date +%Y%m%d-%H%M%S).log"
  exec 3>&1 4>&2
  exec > >(tee -a "$LOG") 2>&1

  printf '\033]0;PhD Tracker setup\007'
  say "PhD Tracker setup"
  say ""
  say "This will:"
  say "  - install Apple's command line tools, if they're missing"
  say "  - download PhD Tracker to $APP_DIR"
  say "  - set up its Python environment"
  say "  - create your data folder: $DATA_DIR"
  say "  - sign you in to Claude, for the research features"
  say ""
  say "It's safe to run again. Your data is only touched to bring the database"
  say "up to date, and that takes a backup first."
  say ""
  ask "Press Return to start, or close this window to cancel. "

  # ── 1. Apple command line tools (git) ────────────────────────────────────
  step "Apple command line tools"
  if xcode-select -p >/dev/null 2>&1; then
    ok "Already installed."
  else
    xcode-select --install >/dev/null 2>&1
    ok "A window has opened asking to install the command line developer tools."
    ok "Click Install, agree to the licence, and wait for it to finish."
    ok "This can take 10-20 minutes; setup carries on by itself afterwards."
    ok "(If you clicked Not Now, close this window and run the setup line again.)"
    local waited=0
    until xcode-select -p >/dev/null 2>&1; do
      sleep 10
      waited=$((waited + 10))
      if [ $((waited % 60)) -eq 0 ]; then
        ok "Still waiting... ($((waited / 60)) min)"
      fi
      if [ "$waited" -ge 3600 ]; then
        fail "the command line tools didn't finish installing within an hour. Once they're installed, run the setup line again."
      fi
    done
    ok "Installed."
  fi
  git --version >/dev/null 2>&1 || fail "git isn't working, even though the command line tools are installed."

  # ── 2. Python 3.12+ ──────────────────────────────────────────────────────
  step "Python"
  local py
  py="$(find_python)" || fail "no Python 3.12 or newer found. Install Python from python.org (3.12 or newer), then run the setup line again."
  ok "Using $py (Python $("$py" -c 'import platform; print(platform.python_version())'))."

  # ── 3. The app itself ────────────────────────────────────────────────────
  step "Download PhD Tracker"
  if [ -d "$APP_DIR/.git" ]; then
    local origin
    origin="$(git -C "$APP_DIR" remote get-url origin 2>/dev/null)"
    case "$origin" in
      *"$REPO_PATH"|*"$REPO_PATH.git"|*"$REPO_PATH/") ;;
      *) fail "$APP_DIR already exists but isn't PhD Tracker. Rename or move that folder, then run the setup line again." ;;
    esac
    git -C "$APP_DIR" pull --ff-only \
      || fail "couldn't update the existing copy in $APP_DIR (see the messages above)."
    ok "Updated the existing copy in $APP_DIR."
  elif [ -e "$APP_DIR" ]; then
    fail "$APP_DIR already exists but isn't PhD Tracker. Rename or move it, then run the setup line again."
  else
    git clone --quiet "$REPO_URL" "$APP_DIR" \
      || fail "couldn't download PhD Tracker. Check your internet connection and run the setup line again."
    ok "Downloaded to $APP_DIR."
  fi

  # ── 4. Python environment ────────────────────────────────────────────────
  step "Python environment"
  local venv="$APP_DIR/backend/.venv"
  local venv_py="$venv/bin/python"
  if [ -x "$venv_py" ] && py_version_ok "$venv_py" >/dev/null; then
    ok "Already set up."
  else
    # Missing or broken (e.g. made by a Python that has since been removed). It
    # holds no data of yours, so it is simply rebuilt.
    rm -rf "$venv"
    "$py" -m venv "$venv" || fail "couldn't create the Python environment."
    ok "Created."
  fi
  ok "Installing the app's components (this can take a few minutes)..."
  (cd "$APP_DIR/backend" && "$venv_py" -m pip install --quiet --disable-pip-version-check -e .) \
    || fail "couldn't install the app's components. Check your internet connection and run the setup line again."
  ok "Components installed."

  # ── 5. Data folder and database ──────────────────────────────────────────
  step "Your data folder"
  (cd "$APP_DIR/backend" && "$venv_py" -m app.init_data_dir) || fail "couldn't create the data folder."
  (cd "$APP_DIR/backend" && "$venv_py" -m app.migrate)
  case $? in
    0) ;;
    3) fail "your data was last used by a newer version of PhD Tracker. Nothing was changed." ;;
    *) fail "couldn't set up the database (see the messages above)." ;;
  esac

  # ── 6. Claude sign-in ────────────────────────────────────────────────────
  step "Sign in to Claude"
  # The app uses the Claude tool bundled with its SDK, so that is the one to
  # sign in with. A subscription sign-in, never API billing.
  local cli
  cli="$("$venv_py" -c 'import pathlib, claude_agent_sdk as s; p = pathlib.Path(s.__file__).parent / "_bundled" / "claude"; print(p if p.is_file() else "")' 2>/dev/null)"
  [ -n "$cli" ] || cli="$(command -v claude 2>/dev/null)"
  local signed_in=0
  if [ -z "$cli" ]; then
    warn "couldn't find the Claude sign-in tool, so research won't work yet. Everything else will."
  elif "$cli" auth status >/dev/null 2>&1; then
    ok "Already signed in."
    signed_in=1
  else
    ok "PhD Tracker's research features run on your own Claude account."
    ok "Your browser will open: sign in with the account that has your Claude subscription."
    ask "    Press Return to continue. "
    "$cli" auth login </dev/tty >&3 2>&4
    if "$cli" auth status >/dev/null 2>&1; then
      ok "Signed in."
      signed_in=1
    else
      warn "not signed in, so research won't work yet. Everything else will. Run the setup line again to retry."
    fi
  fi

  # ── Done ─────────────────────────────────────────────────────────────────
  step "Done"
  say "PhD Tracker is set up."
  say "  App:  $APP_DIR"
  say "  Data: $DATA_DIR"
  [ "$signed_in" -eq 1 ] || say "  Claude: not signed in yet (research won't work until you are)"
  say ""
  say "In the folder that just opened, double-click 'Open PhD Tracker' to start it,"
  say "and 'Update PhD Tracker' to get new versions."
  say ""
  say "A copy of this setup's output is saved in:"
  say "  $LOG"
  open "$APP_DIR"
  say ""
  ask "Open PhD Tracker now? [Y/n] "
  case "$ANSWER" in
    [nN]*) ;;
    *) open "$APP_DIR/Open PhD Tracker.command" ;;
  esac
  exit 0
}

main "$@"; exit $?
