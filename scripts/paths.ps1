# Where things are, and installing the Home Base and the desktop app. Dot-source it:
#   . "$PSScriptRoot\paths.ps1"

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ServerDir = Join-Path $RepoRoot "server"
$MobileDir = Join-Path $RepoRoot "mobile"
$DesktopDir = Join-Path $RepoRoot "desktop"
$LaunchDir = Join-Path $RepoRoot "launch"
$Python = Join-Path $ServerDir ".venv\Scripts\python.exe"
$DesktopPython = Join-Path $DesktopDir ".venv\Scripts\python.exe"

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

# Install a part (server or desktop) into its own .venv, or update it when its pyproject.toml changed
# since last time. $Extras: "" for the app only, or e.g. "dev" / "build" (a stamp in .venv remembers).
function Install-Part($Dir, $Extras, $Label) {
    $venvPython = Join-Path $Dir ".venv\Scripts\python.exe"
    $stamp = Join-Path $Dir ".venv\budget-buddy-install.txt"
    $hash = (Get-FileHash (Join-Path $Dir "pyproject.toml") -Algorithm SHA256).Hash
    if ((Test-Path $venvPython) -and (Test-Path $stamp)) {
        $was = (Get-Content $stamp -Raw).Trim() -split " ", 2
        $had = if ($was.Count -gt 1) { $was[1] -split "," } else { @() }
        $want = if ($Extras) { $Extras -split "," } else { @() }
        if ($was[0] -eq $hash -and -not ($want | Where-Object { $had -notcontains $_ })) { return }
    }
    Assert-Python
    Write-Host "Installing $Label (this can take a few minutes the first time)..."
    Push-Location $Dir
    try {
        if (-not (Test-Path $venvPython)) { py -3 -m venv .venv }
        & $venvPython -m pip install --quiet --upgrade pip
        $target = if ($Extras) { ".[$Extras]" } else { "." }
        & $venvPython -m pip install --quiet -e $target
        if ($LASTEXITCODE -ne 0) { throw "Installing $Label failed." }
        Set-Content -Path $stamp -Encoding ASCII -Value "$hash $Extras"
    } finally { Pop-Location }
}

# The Home Base. -Dev adds the developer tools (tests, linter) that testers' setup uses.
function Install-HomeBase([switch]$Dev) {
    Install-Part $ServerDir $(if ($Dev) { "dev" } else { "" }) "the Home Base"
}
