@echo off
REM Double-click launcher for update-data.ps1 (runs PowerShell for this script only, without changing system policy)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update-data.ps1" %*
pause
