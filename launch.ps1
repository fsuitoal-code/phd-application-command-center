# ===================================================================
#  PhD Application Command Center - Windows dev launcher
#  - starts backend (:8000) and frontend (:5173) in their own windows
#  - waits until BOTH are actually healthy (the frontend's /api proxy
#    returns HTTP 500 while the backend is still starting)
#  - opens the app in a DEDICATED Edge app-mode window (own profile)
#  - when that Edge window is closed, kills both server windows
# ===================================================================

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

$root        = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir  = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$python      = Join-Path $backendDir '.venv\Scripts\python.exe'
# Backend binds IPv4 (127.0.0.1); the Vite frontend binds IPv6 (::1). Probe each
# on the address it actually listens on -- using "localhost" for the backend can
# resolve to ::1 and wrongly report it as never becoming healthy.
$url         = 'http://localhost:5173'
$health      = 'http://127.0.0.1:8000/api/health'

# --- resolve the data directory --------------------------------------
# PHDTRACKER_DATA_DIR, if set (read from the user environment too, in case this
# process was started before it was defined), else %LOCALAPPDATA%\PhDTracker.
#
# Caution: %LOCALAPPDATA% is subject to MSIX copy-on-write virtualization. A
# process running under a packaged app (e.g. a server started from inside a
# Store-packaged desktop app) that WRITES to %LOCALAPPDATA%\PhDTracker gets a
# private shadow copy under
#   %LOCALAPPDATA%\Packages\<pkg>\LocalCache\Local\PhDTracker\
# while this launcher keeps reading the real one -- two diverging databases.
# If you ever run the app that way, set PHDTRACKER_DATA_DIR (as a user
# environment variable) to a folder outside AppData\Local.
if (-not $env:PHDTRACKER_DATA_DIR) {
  $env:PHDTRACKER_DATA_DIR = [Environment]::GetEnvironmentVariable('PHDTRACKER_DATA_DIR', 'User')
}
if (-not $env:PHDTRACKER_DATA_DIR) {
  $env:PHDTRACKER_DATA_DIR = Join-Path $env:LOCALAPPDATA 'PhDTracker'
}

function Show-Error($msg) { [System.Windows.Forms.MessageBox]::Show($msg, 'PhD Tracker') | Out-Null }

if (-not (Test-Path $python)) {
  Show-Error "Backend virtualenv not found at:`n$python`n`nRun the one-time setup in README.md first."
  exit 1
}

# --- clear any stale servers on our ports first ----------------------
# Prevents a previous (or crashed) run from lingering and serving stale
# 500s while a relaunch fails to bind the port.
function Stop-Port([int]$port) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
      Start-Process taskkill -ArgumentList @('/PID', $_, '/T', '/F') -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue
    }
}
Stop-Port 8000
Stop-Port 5173
Start-Sleep -Milliseconds 500

# --- ensure the database schema is up to date (forward-only) ---------
# The backend does NOT create tables on startup; if it connects to an
# unmigrated DB it fails every query with "no such table: programs".
# Migrate before starting the server. Rule 10: snapshot the DB first.
# Derive this from the resolution above, NOT from %LOCALAPPDATA% directly --
# otherwise the backup below could check a path the app doesn't use and skip.
$dbDir  = $env:PHDTRACKER_DATA_DIR
$dbFile = Join-Path $dbDir 'phdtracker.sqlite3'
$python = Join-Path $backendDir '.venv\Scripts\python.exe'

# First run only. app/paths.py refuses to conjure a data directory, so that a
# missing or wrong pin fails loudly instead of handing you a blank app. That
# makes creating one a deliberate answer to this prompt.
if (-not (Test-Path $dbDir)) {
  $answer = [System.Windows.Forms.MessageBox]::Show(
    "No PhD Tracker database was found at:`n$dbDir`n`nCreate a new, empty one there?`n`nIf your database should already exist, choose No -- starting now would give you a blank app and leave the real one untouched elsewhere.",
    'PhD Tracker',
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Warning)
  if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { exit 1 }
  $init = Start-Process -FilePath $python -WorkingDirectory $backendDir -PassThru -Wait -WindowStyle Hidden `
            -ArgumentList '-m','app.init_data_dir'
  if ($init.ExitCode -ne 0) {
    Show-Error "Could not create the data directory (app.init_data_dir exited $($init.ExitCode)). Nothing was started."
    exit 1
  }
}

if (Test-Path $dbFile) {
  # Go through app.backup, NOT Copy-Item: it uses SQLite's online-backup API,
  # which produces a consistent snapshot even while the DB is open (WAL-safe).
  # A raw file copy can miss commits that still live in the -wal sidecar.
  $backup = Start-Process -FilePath $python -WorkingDirectory $backendDir -PassThru -Wait -WindowStyle Hidden `
              -ArgumentList '-m','app.backup'
  if ($backup.ExitCode -ne 0) {
    Show-Error "Could not back up the database before migrating (app.backup exited $($backup.ExitCode)). Nothing was migrated."
    exit 1
  }
}
$alembic    = Join-Path $backendDir '.venv\Scripts\alembic.exe'
$migrateLog = Join-Path $env:TEMP 'phd-migrate.log'
$migrate = Start-Process -FilePath $alembic -WorkingDirectory $backendDir -PassThru -Wait -WindowStyle Hidden `
             -ArgumentList 'upgrade','head' `
             -RedirectStandardOutput $migrateLog -RedirectStandardError "$migrateLog.err"
if ($migrate.ExitCode -ne 0) {
  $detail = (Get-Content "$migrateLog.err" -ErrorAction SilentlyContinue | Select-Object -Last 8) -join "`n"
  Show-Error "Database migration failed (alembic upgrade head exited $($migrate.ExitCode)).`n`n$detail"
  exit 1
}

# --- start the two dev servers in their own visible windows ----------
# Plain cmd windows: uvicorn logs to stderr, and piping a native command's
# stderr through PowerShell (2>&1 | Tee-Object) makes PS 5.1 wrap every line as
# a red NativeCommandError. cmd shows uvicorn's output verbatim, no noise.
# cmd /s /k " ... " keeps the inner quoted paths intact.
# NOTE: no --reload. This venv's base is a pythoncore/PyManager runtime and
# uvicorn's --reload spawns its worker under the BASE interpreter (which lacks
# the venv packages) -> every request 500s. Single-process runs in the venv.
$backendInner  = 'title PhD Tracker - backend & cd /d "'  + $backendDir  + '" & "' + $python + '" -m uvicorn app.main:app --port 8000'
$frontendInner = 'title PhD Tracker - frontend & cd /d "' + $frontendDir + '" & npm run dev'

$backend  = Start-Process cmd.exe -ArgumentList ('/s /k " ' + $backendInner  + ' "') -PassThru
$frontend = Start-Process cmd.exe -ArgumentList ('/s /k " ' + $frontendInner + ' "') -PassThru

# --- wait until the BACKEND is healthy (max 45s) ---------------------
function Wait-Ok($uri, $seconds) {
  $deadline = (Get-Date).AddSeconds($seconds)
  do {
    Start-Sleep -Milliseconds 500
    try { $ok = (Invoke-WebRequest -UseBasicParsing -Uri $uri -TimeoutSec 2).StatusCode -eq 200 }
    catch { $ok = $false }
  } until ($ok -or (Get-Date) -gt $deadline)
  return $ok
}

$backendOk  = Wait-Ok $health 45
$frontendOk = Wait-Ok $url    30

if (-not $backendOk) {
  Show-Error "The backend did not become healthy in time.`n`nCheck the 'PhD Tracker - backend' window for the error."
}

# --- locate Edge -----------------------------------------------------
$edgeExe = $null
foreach ($p in @(
    (Join-Path $env:ProgramFiles       'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:LOCALAPPDATA        'Microsoft\Edge\Application\msedge.exe'))) {
  if (Test-Path $p) { $edgeExe = $p; break }
}

if ($edgeExe) {
  # Dedicated, throwaway profile => a distinct browser process we can wait on,
  # and a window fully separate from the user's normal Edge.
  $edgeProfile = Join-Path $env:TEMP ('phd-tracker-edge-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
  $edge = Start-Process -FilePath $edgeExe -PassThru -ArgumentList @(
    "--app=$url",
    '--new-window',
    '--no-first-run',
    '--no-default-browser-check',
    "--user-data-dir=$edgeProfile"
  )
  $edge.WaitForExit()

  # Edge window closed -> tear everything down.
  foreach ($proc in @($backend, $frontend)) {
    if ($proc -and -not $proc.HasExited) {
      Start-Process taskkill -ArgumentList @('/PID', $proc.Id, '/T', '/F') -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue
    }
  }
  Remove-Item $edgeProfile -Recurse -Force -ErrorAction SilentlyContinue
}
else {
  # No Edge found: fall back to the default browser and leave the servers
  # running (we can't tie their lifetime to the browser in that case).
  Start-Process $url
}
