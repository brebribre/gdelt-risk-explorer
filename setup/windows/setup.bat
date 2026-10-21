@echo off
REM Double-click launcher for setup.ps1 (runs PowerShell for this script only, without changing system policy)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
pause
