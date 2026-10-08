# One-time setup for testing Budget Buddy on Windows.
# Installs the Home Base (Python) and the phone app's tools (Node.js). Safe to run again.
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

. "$PSScriptRoot\test-settings.ps1"

Write-Host "Setting up Budget Buddy for testing..." -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python isn't installed. Install Python 3.12 or newer from https://www.python.org/downloads/ (tick 'Add to PATH'), then run this again." -ForegroundColor Yellow
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js isn't installed. Install the LTS version from https://nodejs.org/, then run this again." -ForegroundColor Yellow
    exit 1
}

Write-Host "1/2  Home Base (this can take a few minutes the first time)..."
Push-Location $ServerDir
try {
    if (-not (Test-Path $Python)) { py -3 -m venv .venv }
    & $Python -m pip install --quiet --upgrade pip
    & $Python -m pip install --quiet -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { throw "Installing the Home Base failed." }
} finally { Pop-Location }

Write-Host "2/2  Phone app tools..."
Push-Location $MobileDir
try {
    npm ci --no-audit --no-fund --loglevel=error
    if ($LASTEXITCODE -ne 0) { throw "Installing the phone app tools failed." }
} finally { Pop-Location }

Write-Host ""
Write-Host "All set. Next:" -ForegroundColor Green
Write-Host "  1. scripts\start-test-server.ps1   (leave that window open)"
Write-Host "  2. scripts\load-demo-data.ps1      (fills it with made-up data)"
Write-Host "See docs\guide\set-up-for-testing.md for the full walkthrough."
