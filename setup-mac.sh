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
#
# The screen shows one line per step. Everything the steps themselves print
# goes to a log in ~/Library/Logs/PhDTracker/, and a failed step shows its last
# lines on screen.

REPO_URL="https://github.com/fsuitoal-code/phd-application-command-center.git"
REPO_PATH="fsuitoal-code/phd-application-command-center"
APP_DIR="$HOME/PhDTracker"
DATA_DIR="$HOME/Library/Application Support/PhDTracker"
LOG_DIR="$HOME/Library/Logs/PhDTracker"
SHORTCUTS_DIR="$HOME/Desktop/PhD Tracker"
SHORTCUTS_MARKER=".phdtracker-shortcuts"

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

build_icns() {
  # build_icns <square.png> <out.icns> -- a full set of macOS icon sizes from
  # one PNG, with the tools every Mac has (sips, iconutil).
  local set size
  set="$(dirname "$2")/AppIcon.iconset"
  mkdir -p "$set" || return 1
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$1" --out "$set/icon_${size}x${size}.png" || return 1
    sips -z $((size * 2)) $((size * 2)) "$1" --out "$set/icon_${size}x${size}@2x.png" || return 1
  done
  iconutil -c icns "$set" -o "$2"
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

make_shortcuts_folder() {
  # make_shortcuts_folder <icon.png> [icon.icns] -- the "PhD Tracker" folder on
  # the Desktop, wearing the app icon and holding the Open and Update
  # shortcuts. The app itself stays in ~/PhDTracker (a synced Desktop would
  # break it). Only ever changes a folder this setup made: it holds a marker.
  local png="$1" icns="${2:-}"
  if [ -e "$SHORTCUTS_DIR" ] && [ ! -e "$SHORTCUTS_DIR/$SHORTCUTS_MARKER" ]; then
    return 1
  fi
  mkdir -p "$SHORTCUTS_DIR" || return 1
  printf 'Made by PhD Tracker setup. The app itself is in ~/PhDTracker.\n' \
    >"$SHORTCUTS_DIR/$SHORTCUTS_MARKER" || return 1
  make_shortcut "$SHORTCUTS_DIR" "Open PhD Tracker" "$APP_DIR/Open PhD Tracker.command" "$icns" || return 1
  make_shortcut "$SHORTCUTS_DIR" "Update PhD Tracker" "$APP_DIR/Update PhD Tracker.command" "$icns" || return 1
  set_icon "$png" "$SHORTCUTS_DIR" || printf 'Could not set the folder icon.\n' >>"$LOG"
  return 0
}

make_shortcut() {
  # make_shortcut <dir> <name> <launcher.command> [icon.icns] -- a small app
  # that opens the launcher in Terminal. It is an app rather than an alias so
  # it can carry its own icon, which updates to the launcher (a replaced file)
  # would otherwise strip. Only ever replaces a shortcut this setup made,
  # recognised by its bundle identifier.
  local name="$2" target="$3" icns="${4:-}"
  local app="$1/$name.app"
  local id
  id="local.phdtracker.$(printf '%s' "$name" | tr 'A-Z ' 'a-z-')"
  if [ -e "$app" ] && ! grep -q "<string>$id</string>" "$app/Contents/Info.plist" 2>/dev/null; then
    return 1
  fi
  rm -rf "$app"
  mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources" || return 1
  cat >"$app/Contents/Info.plist" <<EOF || return 1
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$name</string>
  <key>CFBundleDisplayName</key><string>$name</string>
  <key>CFBundleIdentifier</key><string>$id</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
EOF
  cat >"$app/Contents/MacOS/launch" <<EOF || return 1
#!/bin/bash
# Opens PhD Tracker's "$name" launcher in Terminal. Made by PhD Tracker's setup.
target="$target"
if [ -e "\$target" ]; then
  exec /usr/bin/open "\$target"
fi
/usr/bin/osascript -e 'display alert "PhD Tracker" message "PhD Tracker is no longer in its usual folder. Run the setup line again to repair this shortcut." as critical' >/dev/null 2>&1
EOF
  chmod +x "$app/Contents/MacOS/launch" || return 1
  if [ -n "$icns" ]; then
    cp "$icns" "$app/Contents/Resources/AppIcon.icns" || return 1
  fi
  touch "$app"
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
  say "This takes a few minutes. Near the end you'll sign in to Claude in your browser."
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

  # ── 3. The app itself ────────────────────────────────────────────────────
  if [ -d "$APP_DIR/.git" ]; then
    local origin
    origin="$(git -C "$APP_DIR" remote get-url origin 2>/dev/null)"
    case "$origin" in
      *"$REPO_PATH"|*"$REPO_PATH.git"|*"$REPO_PATH/") ;;
      *) fail "$APP_DIR already exists but isn't PhD Tracker. Rename or move that folder, then run the setup line again." ;;
    esac
    quietly git -C "$APP_DIR" pull --ff-only \
      || fail "Couldn't update the copy of PhD Tracker in $APP_DIR." show-log
    ok "PhD Tracker is up to date"
  elif [ -e "$APP_DIR" ]; then
    fail "$APP_DIR already exists but isn't PhD Tracker. Rename or move it, then run the setup line again."
  else
    quietly git clone "$REPO_URL" "$APP_DIR" \
      || fail "Couldn't download PhD Tracker. Check your internet connection and run the setup line again." show-log
    ok "Downloaded PhD Tracker"
  fi

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

  # ── 6. The PhD Tracker folder on the Desktop ─────────────────────────────
  # The first write to the Desktop makes macOS ask whether Terminal may access
  # it, so say so first.
  doing "Adding a PhD Tracker folder to your Desktop (if macOS asks about your Desktop, click Allow)"
  local logo="$APP_DIR/frontend/public/logo-512.png"
  local tmp icns="" shortcuts=0
  tmp="$(mktemp -d 2>/dev/null)"
  if [ -n "$tmp" ] && quietly build_icns "$logo" "$tmp/AppIcon.icns"; then
    icns="$tmp/AppIcon.icns"
  else
    printf 'Could not build the shortcut icon; the shortcuts get the default one.\n' >>"$LOG"
  fi
  if make_shortcuts_folder "$logo" "$icns"; then
    ok "PhD Tracker folder on your Desktop"
    shortcuts=1
  else
    warn "Couldn't add the PhD Tracker folder to your Desktop. The Open and Update launchers are in the PhDTracker folder in your home folder instead."
  fi
  [ -n "$tmp" ] && rm -rf "$tmp"

  # ── 7. Claude sign-in ────────────────────────────────────────────────────
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
  if [ "$shortcuts" -eq 1 ]; then
    say "All set. In the PhD Tracker folder on your Desktop (it just opened):"
    say "  \"Open PhD Tracker\" starts it, and \"Update PhD Tracker\" gets new versions."
    open "$SHORTCUTS_DIR"
  else
    say "All set. PhD Tracker is in the folder that just opened:"
    say "  double-click \"Open PhD Tracker\" to start it, and"
    say "  \"Update PhD Tracker\" to get new versions."
    open "$APP_DIR"
  fi
  say ""
  say "(A record of this setup is in ~/Library/Logs/PhDTracker.)"
  say ""
  ask "Open PhD Tracker now? [Y/n] "
  case "$ANSWER" in
    [nN]*) ;;
    *) open "$APP_DIR/Open PhD Tracker.command" ;;
  esac
  exit 0
}

main "$@"; exit $?
