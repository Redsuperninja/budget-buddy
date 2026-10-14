# Install (or remove) the Budget Buddy desktop app for this Windows user. No admin rights needed; safe to run
# again to update. Used by the release download ("Install Budget Buddy.bat") and by scripts\release\install-desktop.ps1.
#
#   install.ps1 [-From <folder with Budget Buddy.exe>] [-NoDesktopShortcut]
#   install.ps1 -Uninstall      removes the app and its shortcuts; your data folder is kept
#
# It copies the app to %LOCALAPPDATA%\Programs\Budget Buddy and adds Start menu and desktop shortcuts. Your data
# (%LOCALAPPDATA%\BudgetBuddy) is never touched.

param(
    [string]$From = (Join-Path $PSScriptRoot "Budget Buddy"),
    [switch]$NoDesktopShortcut,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$Target = Join-Path $env:LOCALAPPDATA "Programs\Budget Buddy"
$Exe = Join-Path $Target "Budget Buddy.exe"
$StartMenuLink = Join-Path ([Environment]::GetFolderPath("Programs")) "Budget Buddy.lnk"
$DesktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "Budget Buddy.lnk"
# Listed in Windows Settings, Apps, so it can be removed from there too (per user, no admin rights).
$AppsEntry = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetBuddy"

if (Get-Process -Name "Budget Buddy", "Budget Buddy Home Base" -ErrorAction SilentlyContinue) {
    Write-Host "Budget Buddy is running. Close its window and choose Quit on its tray icon, then run this again." -ForegroundColor Yellow
    exit 1
}

if ($Uninstall) {
    foreach ($path in $Target, $StartMenuLink, $DesktopLink, $AppsEntry) {
        if (Test-Path $path) { Remove-Item -Recurse -Force $path }
    }
    # "Start with Windows" (desktop/budget_buddy_desktop/autostart.py), if it was ticked.
    Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "Budget Buddy" -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "Budget Buddy is removed. Your data is still in $(Join-Path $env:LOCALAPPDATA 'BudgetBuddy')." -ForegroundColor Green
    Write-Host "Delete that folder too only if you never want your budget again (keep your recovery phrase either way)."
    exit 0
}

if (-not (Test-Path (Join-Path $From "Budget Buddy.exe"))) {
    Write-Host "Budget Buddy.exe wasn't found in $From. Unzip the whole download first, then run this again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing to $Target..."
if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
Copy-Item -Recurse $From $Target
# Files from a downloaded zip are marked "from the internet"; the installed copy is the user's own choice.
Get-ChildItem -Recurse -File $Target | Unblock-File
Copy-Item $PSCommandPath (Join-Path $Target "install.ps1")  # so Settings, Apps can uninstall it later

function New-Shortcut($Path) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Path)
    $link.TargetPath = $Exe
    $link.WorkingDirectory = $Target
    $link.Description = "Budget Buddy: your budget and tax records, on this computer"
    $link.Save()
}

New-Shortcut $StartMenuLink
if (-not $NoDesktopShortcut) { New-Shortcut $DesktopLink }

$versionFile = Join-Path $Target "version.txt"  # written by scripts\release\make-release.ps1
New-Item -Path $AppsEntry -Force | Out-Null
$entry = @{
    DisplayName = "Budget Buddy"; Publisher = "Budget Buddy"; DisplayIcon = $Exe; InstallLocation = $Target
    UninstallString = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Target\install.ps1`" -Uninstall"
    DisplayVersion = $(if (Test-Path $versionFile) { (Get-Content $versionFile -Raw).Trim() } else { "dev" })
}
foreach ($name in $entry.Keys) { Set-ItemProperty -Path $AppsEntry -Name $name -Value $entry[$name] }
Set-ItemProperty -Path $AppsEntry -Name NoModify -Value 1 -Type DWord
Set-ItemProperty -Path $AppsEntry -Name NoRepair -Value 1 -Type DWord

Write-Host ""
Write-Host "Installed. Open Budget Buddy from the Start menu or the desktop." -ForegroundColor Green
Write-Host "To have it ready when Windows starts, right-click its tray icon and tick 'Start with Windows'."
