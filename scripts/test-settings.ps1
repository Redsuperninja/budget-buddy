# Settings shared by the user-testing scripts. Dot-source it: . "$PSScriptRoot\test-settings.ps1"
#
# The test Home Base is kept completely apart from real use:
#   - its own data folder (its own encryption key in the password vault, too),
#   - its own port (8766; the real Home Base uses 8765),
# so demo data can never end up in your real data.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ServerDir = Join-Path $RepoRoot "server"
$MobileDir = Join-Path $RepoRoot "mobile"
$Python = Join-Path $ServerDir ".venv\Scripts\python.exe"

$TestDataDir = Join-Path $env:LOCALAPPDATA "BudgetBuddy-Test"
$TestPort = 8766

function Assert-SetUp {
    if (-not (Test-Path $Python)) {
        Write-Host "Budget Buddy isn't set up on this computer yet. Run scripts\setup.ps1 first." -ForegroundColor Yellow
        exit 1
    }
}
