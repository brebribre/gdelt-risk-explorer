# One-time setup for Windows:
# Python virtualenv + API dependencies, web dependencies, first data download.
#
# Usage (PowerShell):  .\setup\windows\setup.ps1 [-Hours 48] [-SkipData]
# Or double-click setup\windows\setup.bat
param(
    [int]$Hours = 48,
    [switch]$SkipData
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

# Native commands don't throw on failure in PowerShell; check the exit code ourselves.
function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Exe $($Arguments -join ' ')" }
}

# Find Python 3.10+. Try the 'py' launcher first; 'python' may be the Microsoft Store shortcut.
$Python = $null
foreach ($candidate in @(@("py", "-3"), @("python"), @("python3"))) {
    if (-not (Get-Command $candidate[0] -ErrorAction SilentlyContinue)) { continue }
    $extra = @($candidate | Select-Object -Skip 1)
    $ok = & $candidate[0] @extra -c "import sys; print(int(sys.version_info >= (3, 10)))" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$ok".Trim() -eq "1") { $Python = $candidate; break }
}
if (-not $Python) {
    Write-Host "X Python 3.10+ not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "X Node.js not found. Install Node.js 18+ from https://nodejs.org/" -ForegroundColor Red
    exit 1
}
$nodeMajor = [int]((node -v).TrimStart("v").Split(".")[0])
if ($nodeMajor -lt 18) {
    Write-Host "X Node.js 18+ required (found $(node -v))" -ForegroundColor Red
    exit 1
}

Write-Host "-> Python virtualenv + API dependencies" -ForegroundColor Cyan
if (-not (Test-Path $VenvPython)) {
    $extra = @($Python | Select-Object -Skip 1)
    Invoke-Checked $Python[0] ($extra + @("-m", "venv", (Join-Path $Root ".venv")))
}
Invoke-Checked $VenvPython @("-m", "pip", "install", "-q", "--upgrade", "pip")
Invoke-Checked $VenvPython @("-m", "pip", "install", "-q", "-r", (Join-Path $Root "server\requirements.txt"))

Write-Host "-> Web dependencies" -ForegroundColor Cyan
Push-Location (Join-Path $Root "web")
try { Invoke-Checked "npm" @("install", "--no-audit", "--no-fund") } finally { Pop-Location }

if ($SkipData) {
    Write-Host "-> Skipping data download" -ForegroundColor Cyan
} else {
    Write-Host "-> Downloading the last ${Hours}h of GDELT data (about 1.35 GB per day; takes a few minutes)" -ForegroundColor Cyan
    Invoke-Checked $VenvPython @((Join-Path $Root "ingest\ingest.py"), "--hours", "$Hours")
}

Write-Host ""
Write-Host "Setup done. Start the app with: .\setup\windows\start.ps1 (or double-click start.bat)" -ForegroundColor Green
