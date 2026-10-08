# Install the built desktop app for this Windows user: copies launch\Budget Buddy\ to
# %LOCALAPPDATA%\Programs\Budget Buddy and adds Start menu and desktop shortcuts. No admin rights
# needed. Safe to run again to update.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install-desktop.ps1 [-NoDesktopShortcut]

param([switch]$NoDesktopShortcut)

. "$PSScriptRoot\paths.ps1"

$Built = Join-Path $LaunchDir "Budget Buddy"
$Target = Join-Path $env:LOCALAPPDATA "Programs\Budget Buddy"
$Exe = Join-Path $Target "Budget Buddy.exe"

if (-not (Test-Path (Join-Path $Built "Budget Buddy.exe"))) {
    Write-Host "Build the app first: double-click 'Build desktop app' in the launch folder." -ForegroundColor Yellow
    exit 1
}
if (Get-Process -Name "Budget Buddy", "Budget Buddy Home Base" -ErrorAction SilentlyContinue) {
    Write-Host "Budget Buddy is running. Close its window and choose Quit on its tray icon, then run this again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing to $Target..."
if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
Copy-Item -Recurse $Built $Target

function New-Shortcut($Path) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Path)
    $link.TargetPath = $Exe
    $link.WorkingDirectory = $Target
    $link.Description = "Budget Buddy: your budget and tax records, on this computer"
    $link.Save()
}

New-Shortcut (Join-Path ([Environment]::GetFolderPath("Programs")) "Budget Buddy.lnk")
if (-not $NoDesktopShortcut) { New-Shortcut (Join-Path ([Environment]::GetFolderPath("Desktop")) "Budget Buddy.lnk") }

Write-Host ""
Write-Host "Installed. Open Budget Buddy from the Start menu or the desktop." -ForegroundColor Green
Write-Host "To have it ready when Windows starts, right-click its tray icon and tick 'Start with Windows'."
