@echo off
REM ===================================================================
REM  PhD Application Command Center - Windows dev launcher
REM  Thin wrapper: launches launch.ps1 hidden so no extra console
REM  window lingers. launch.ps1 starts both dev servers, opens a
REM  dedicated Edge app window, and kills the servers when it closes.
REM ===================================================================
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0launch.ps1"
exit
