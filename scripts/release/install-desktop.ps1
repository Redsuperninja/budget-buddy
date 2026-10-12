# Install the desktop app built by build-desktop.ps1 (launch\Budget Buddy\) for this Windows user, with Start menu
# and desktop shortcuts. The work is done by packaging\windows\install.ps1, the same installer the release download
# uses. Safe to run again to update.
#
#   powershell -ExecutionPolicy Bypass -File scripts\release\install-desktop.ps1 [-NoDesktopShortcut]

param([switch]$NoDesktopShortcut)

. "$PSScriptRoot\..\paths.ps1"

$Built = Join-Path $LaunchDir "Budget Buddy"
if (-not (Test-Path (Join-Path $Built "Budget Buddy.exe"))) {
    Write-Host "Build the app first: double-click 'Build desktop app' in the launch folder." -ForegroundColor Yellow
    exit 1
}
& (Join-Path $PackagingDir "install.ps1") -From $Built -NoDesktopShortcut:$NoDesktopShortcut
exit $LASTEXITCODE
