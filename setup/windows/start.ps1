# Start the API (port 8787) and the web app (port 5173). Ctrl+C stops both.
#
# Usage (PowerShell):  .\setup\windows\start.ps1
# Or double-click setup\windows\start.bat
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "X Not set up yet. Run: .\setup\windows\setup.ps1" -ForegroundColor Red; exit 1
}
if (-not (Test-Path (Join-Path $Root "web\node_modules"))) {
    Write-Host "X Web dependencies missing. Run: .\setup\windows\setup.ps1 -SkipData" -ForegroundColor Red; exit 1
}
if (-not (Test-Path (Join-Path $Root "data\gdelt.db"))) {
    Write-Host "X No data yet. Run: .\setup\windows\update-data.ps1" -ForegroundColor Red; exit 1
}

$api = Start-Process -FilePath $VenvPython -ArgumentList "`"$(Join-Path $Root 'server\api.py')`"" -NoNewWindow -PassThru

Write-Host "App:     http://localhost:5173"
Write-Host "Swagger: http://localhost:8787/api/docs"
Write-Host "Press Ctrl+C to stop."
Push-Location (Join-Path $Root "web")
try {
    npm run dev
} finally {
    Pop-Location
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force }
}
