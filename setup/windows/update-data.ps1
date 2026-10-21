# Fetch new GDELT batches into data\gdelt.db. Incremental: only downloads batches not stored yet.
# The API can keep running while this runs.
#
# Usage (PowerShell):  .\setup\windows\update-data.ps1 [-Hours 48]
# Or double-click setup\windows\update-data.bat
param([int]$Hours = 48)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "X Not set up yet. Run: .\setup\windows\setup.ps1" -ForegroundColor Red; exit 1
}
& $VenvPython (Join-Path $Root "ingest\ingest.py") --hours $Hours
exit $LASTEXITCODE
