# Where things are, and installing the Home Base. Dot-source it: . "$PSScriptRoot\paths.ps1"

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ServerDir = Join-Path $RepoRoot "server"
$MobileDir = Join-Path $RepoRoot "mobile"
$Python = Join-Path $ServerDir ".venv\Scripts\python.exe"
$InstallStamp = Join-Path $ServerDir ".venv\budget-buddy-install.txt"

# Python 3.12 or newer, through the Windows "py" launcher. Exits with a plain-English message if missing.
function Assert-Python {
    $ok = $false
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $ok = (& py -3 -c "import sys; print(sys.version_info >= (3, 12))" 2>$null) -eq "True"
    }
    if (-not $ok) {
        Write-Host "Budget Buddy needs Python 3.12 or newer. Install it from https://www.python.org/downloads/ (tick 'Add to PATH'), then try again." -ForegroundColor Yellow
        exit 1
    }
}

# Install the Home Base into server\.venv, or update it when its requirements changed since last time.
# -Dev adds the developer tools (tests, linter) that testers' setup uses.
function Install-HomeBase([switch]$Dev) {
    $hash = (Get-FileHash (Join-Path $ServerDir "pyproject.toml") -Algorithm SHA256).Hash
    $mode = if ($Dev) { "dev" } else { "app" }
    if ((Test-Path $Python) -and (Test-Path $InstallStamp)) {
        $was = (Get-Content $InstallStamp -Raw).Trim() -split " "
        if ($was[0] -eq $hash -and ($was[1] -eq "dev" -or $mode -eq "app")) { return }
    }
    Assert-Python
    Write-Host "Installing the Home Base (this can take a few minutes the first time)..."
    Push-Location $ServerDir
    try {
        if (-not (Test-Path $Python)) { py -3 -m venv .venv }
        & $Python -m pip install --quiet --upgrade pip
        $target = if ($Dev) { ".[dev]" } else { "." }
        & $Python -m pip install --quiet -e $target
        if ($LASTEXITCODE -ne 0) { throw "Installing the Home Base failed." }
        Set-Content -Path $InstallStamp -Encoding ASCII -Value "$hash $mode"
    } finally { Pop-Location }
}
