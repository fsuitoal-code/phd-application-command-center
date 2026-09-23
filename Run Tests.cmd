@echo off
REM ===================================================================
REM  PhD Application Command Center - test runner (Windows)
REM  Rebuilds the frontend (frontend/dist is committed and served by
REM  FastAPI on installed copies), then runs the pytest suite.
REM ===================================================================

setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo [ERROR] Backend virtualenv not found at:
  echo         %PYTHON%
  echo Run the one-time setup in README.md first.
  echo.
  pause
  exit /b 1
)

cd /d "%ROOT%backend"
echo Building frontend ...
"%PYTHON%" scripts\build_frontend.py
if errorlevel 1 (
  echo.
  echo [ERROR] Frontend build failed - tests not run.
  echo.
  pause
  exit /b 1
)
echo.
echo Running backend tests ...
echo.
"%PYTHON%" -m pytest %*

echo.
echo Test run finished ^(exit code %ERRORLEVEL%^).
pause
endlocal
