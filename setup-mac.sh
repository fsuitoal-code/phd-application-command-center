#!/bin/bash
# PhD Tracker -- macOS setup.
#
# Run it by pasting this one line into Terminal (it downloads and runs this file):
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/fsuitoal-code/phd-application-command-center/main/setup-mac.sh)"
#
# Python 3.12 or newer must already be installed (python.org). The setup then
# installs Apple's command line tools if they're missing (git needs them),
# downloads the app into a "PhD Tracker" folder on the Desktop, sets up its
# Python environment, creates the data folder and database, and signs you in
# to Claude.
#
# Safe to run again: every step checks before it acts. Your data is kept apart
# from the app, in ~/Library/Application Support/PhDTracker, and is only ever
# touched to bring the database up to date, which takes a backup first.
#
# The screen shows one line per step. Everything the steps themselves print
# goes to a log in ~/Library/Logs/PhDTracker/, and a failed step shows its last
# lines on screen.

REPO_URL="https://github.com/fsuitoal-code/phd-application-command-center.git"
REPO_PATH="fsuitoal-code/phd-application-command-center"
APP_DIR="$HOME/Desktop/PhD Tracker"
DATA_DIR="$HOME/Library/Application Support/PhDTracker"
LOG_DIR="$HOME/Library/Logs/PhDTracker"
# An earlier version of this setup made a Desktop folder of the same name that
# held only shortcuts. It is recognised by this marker and replaced by the app.
OLD_SHORTCUTS_MARKER=".phdtracker-shortcuts"

say()   { printf '%s\n' "$*"; }
ok()    { printf '  ✓  %s\n' "$*"; }
doing() { printf '  …  %s\n' "$*"; }
note()  { printf '     %s\n' "$*"; }
warn()  { printf '  !  %s\n' "$*"; }

fail() {
  # fail <message> [show-log] -- stops the setup. With a second argument, the
  # last lines of the log (the failed step's own output) are shown as well.
  local recent=""
  [ -n "${2:-}" ] && recent="$(tail -n 12 "$LOG")"
  printf '  ✗  %s\n' "$1"
  if [ -n "$recent" ]; then
    printf '\n     The last lines of the setup log:\n'
    printf '%s\n' "$recent" | sed 's/^/       /'
  fi
  printf '\n     Setup stopped. If you are stuck, send this file to whoever is helping you:\n'
  printf '       %s\n' "$LOG"
  exit 1
}

quietly() {
  # quietly <command...> -- runs it with its output going to the log only.
  "$@" >>"$LOG" 2>&1
}

ask() {
  # ask <prompt> -- reads the answer from the keyboard into $ANSWER.
  ANSWER=""
  read -r -p "$1" ANSWER </dev/tty || ANSWER=""
}

sign_in() {
  # sign_in <claude-cli> -- runs the interactive sign-in on the real terminal.
  # The CLI is built on Bun, which watches its input with kqueue, and macOS
  # kqueue rejects anything opened through the /dev/tty alias (EINVAL). So it
  # gets the terminal's own device: the inherited input when that is the
  # terminal, otherwise the device path of this process's controlling terminal.
  if [ -t 0 ]; then
    "$1" auth login >&3 2>&4
  else
    local dev
    dev="/dev/$(ps -o tty= -p $$ | tr -d ' ')"
    [ -c "$dev" ] || return 1
    "$1" auth login <"$dev" >&3 2>&4
  fi
}

set_icon() {
  # set_icon <image> <path> -- gives a file or folder a custom Finder icon,
  # through macOS's own NSWorkspace (reached with the built-in osascript).
  osascript -l JavaScript -e '
    ObjC.import("AppKit");
    function run(argv) {
      var image = $.NSImage.alloc.initWithContentsOfFile(argv[0]);
      if (image.isNil()) return "no image";
      return $.NSWorkspace.sharedWorkspace.setIconForFileOptions(image, argv[1], 0) ? "ok" : "failed";
    }' "$1" "$2" 2>/dev/null | grep -qx ok
}

apply_icons() {
  # The app logo on the folder and on its Open and Update launchers. Cosmetic,
  # so a failure only goes to the log. (The Update launcher does the same after
  # each update, since a replaced launcher file loses its icon.)
  local logo="$APP_DIR/frontend/public/logo-512.png" item
  for item in "$APP_DIR" "$APP_DIR/Open PhD Tracker.command" "$APP_DIR/Update PhD Tracker.command"; do
    set_icon "$logo" "$item" || printf 'Could not set the icon on %s\n' "$item" >>"$LOG"
  done
}

app_dir_state() {
  # Prints what is at APP_DIR: absent, ours (a clone of this app),
  # old-shortcuts (the earlier shortcuts folder), or other (not ours: leave it).
  if [ ! -e "$APP_DIR" ]; then
    echo absent
  elif [ -d "$APP_DIR/.git" ]; then
    case "$(git -C "$APP_DIR" remote get-url origin 2>/dev/null)" in
      *"$REPO_PATH"|*"$REPO_PATH.git"|*"$REPO_PATH/") echo ours ;;
      *) echo other ;;
    esac
  elif [ -e "$APP_DIR/$OLD_SHORTCUTS_MARKER" ]; then
    echo old-shortcuts
  else
    echo other
  fi
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
  say ""
  say "PhD Tracker setup"
  say ""
  say "This takes a few minutes and puts a PhD Tracker folder on your Desktop."
  say "Near the end you'll sign in to Claude in your browser."
  say ""
  ask "Press Return to start. "
  say ""

  # ── 1. Apple command line tools (git) ────────────────────────────────────
  if ! xcode-select -p >/dev/null 2>&1; then
    xcode-select --install >/dev/null 2>&1
    doing "Installing Apple's command line tools"
    note "A window has opened: click Install, then Agree, and wait for it to finish."
    note "This can take 10-20 minutes. Setup carries on by itself afterwards."
    note "(If you clicked Not Now, close this window and run the setup line again.)"
    local waited=0
    until xcode-select -p >/dev/null 2>&1; do
      sleep 10
      waited=$((waited + 10))
      if [ $((waited % 60)) -eq 0 ]; then
        note "still waiting ($((waited / 60)) min)"
      fi
      if [ "$waited" -ge 3600 ]; then
        fail "Apple's command line tools didn't finish installing within an hour. Once they have, run the setup line again."
      fi
    done
  fi
  git --version >/dev/null 2>&1 || fail "git isn't working, even though Apple's command line tools are installed."
  ok "Apple command line tools"

  # ── 2. Python 3.12+ ──────────────────────────────────────────────────────
  local py
  py="$(find_python)" || fail "No Python 3.12 or newer found. Install Python from python.org (3.12 or newer), then run the setup line again."
  printf 'Using %s\n' "$py" >>"$LOG"
  ok "Python $("$py" -c 'import platform; print(platform.python_version())')"

  # ── 3. The app itself, in a folder on the Desktop ────────────────────────
  # The first look at the Desktop makes macOS ask whether Terminal may access
  # it, so say so first.
  doing "Downloading PhD Tracker to your Desktop (if macOS asks about your Desktop, click Allow)"
  local state
  state="$(app_dir_state)"
  case "$state" in
    ours)
      quietly git -C "$APP_DIR" pull --ff-only \
        || fail "Couldn't update the copy of PhD Tracker on your Desktop." show-log
      ok "PhD Tracker is up to date"
      ;;
    other)
      fail "There is already a folder called \"PhD Tracker\" on your Desktop. Rename or move it, then run the setup line again."
      ;;
    *)
      # absent, or the earlier shortcuts-only folder, which the app replaces.
      [ "$state" = old-shortcuts ] && rm -rf "$APP_DIR"
      quietly git clone "$REPO_URL" "$APP_DIR" \
        || fail "Couldn't download PhD Tracker. Check your internet connection. If macOS asked about your Desktop and you clicked Don't Allow, turn Terminal on in System Settings > Privacy & Security > Files and Folders. Then run the setup line again." show-log
      ok "Downloaded PhD Tracker to your Desktop"
      ;;
  esac
  apply_icons

  # ── 4. Python environment ────────────────────────────────────────────────
  local venv="$APP_DIR/backend/.venv"
  local venv_py="$venv/bin/python"
  if ! { [ -x "$venv_py" ] && py_version_ok "$venv_py" >/dev/null; }; then
    # Missing or broken (e.g. made by a Python that has since been removed). It
    # holds no data of yours, so it is simply rebuilt.
    rm -rf "$venv"
    quietly "$py" -m venv "$venv" || fail "Couldn't create PhD Tracker's Python environment." show-log
  fi
  doing "Installing PhD Tracker's components (this takes a few minutes)"
  (cd "$APP_DIR/backend" && quietly "$venv_py" -m pip install --disable-pip-version-check -e .) \
    || fail "Couldn't install PhD Tracker's components. Check your internet connection and run the setup line again." show-log
  ok "Installed PhD Tracker's components"

  # ── 5. Data folder and database ──────────────────────────────────────────
  local had_db=0
  [ -f "$DATA_DIR/phdtracker.sqlite3" ] && had_db=1
  (cd "$APP_DIR/backend" && quietly "$venv_py" -m app.init_data_dir) \
    || fail "Couldn't create your data folder." show-log
  (cd "$APP_DIR/backend" && quietly "$venv_py" -m app.migrate)
  case $? in
    0) ;;
    3) fail "Your data was last used by a newer version of PhD Tracker. Nothing was changed." show-log ;;
    *) fail "Couldn't set up your database." show-log ;;
  esac
  if [ "$had_db" -eq 1 ]; then
    ok "Your data is kept and up to date"
  else
    ok "Created your database"
  fi

  # ── 6. Claude sign-in ────────────────────────────────────────────────────
  # The app uses the Claude tool bundled with its SDK, so that is the one to
  # sign in with. A subscription sign-in, never API billing.
  local cli
  cli="$("$venv_py" -c 'import pathlib, claude_agent_sdk as s; p = pathlib.Path(s.__file__).parent / "_bundled" / "claude"; print(p if p.is_file() else "")' 2>/dev/null)"
  [ -n "$cli" ] || cli="$(command -v claude 2>/dev/null)"
  if [ -z "$cli" ]; then
    warn "Couldn't find the Claude sign-in tool. Research won't work yet; everything else will."
  elif "$cli" auth status >/dev/null 2>&1; then
    ok "Signed in to Claude"
  else
    say ""
    say "  Next, sign in to Claude. Your browser will open: use the account that has"
    say "  your Claude subscription. PhD Tracker's research runs on that account."
    ask "  Press Return to continue. "
    sign_in "$cli"
    say ""
    if "$cli" auth status >/dev/null 2>&1; then
      ok "Signed in to Claude"
    else
      warn "Not signed in to Claude. Research won't work until you are; everything else will."
      note "To try again, run the setup line again."
    fi
  fi

  # ── Done ─────────────────────────────────────────────────────────────────
  say ""
  say "All set. The PhD Tracker folder is on your Desktop (it just opened):"
  say "  \"Open PhD Tracker\" starts it, and \"Update PhD Tracker\" gets new versions."
  say ""
  say "(A record of this setup is in ~/Library/Logs/PhDTracker.)"
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
