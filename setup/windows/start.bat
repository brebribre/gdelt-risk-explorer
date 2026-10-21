@echo off
REM Double-click launcher for start.ps1 (runs PowerShell for this script only, without changing system policy)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
pause
