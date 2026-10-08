# Build the Windows desktop app into launch\Budget Buddy\ (roadmap 22, ADR-0008):
#   Budget Buddy.exe            the window and tray icon (desktop\)
#   home-base\                  the packaged Home Base it starts (server\, with the dashboard files)
# Nobody needs Python to run the result. Then install-desktop.ps1 adds it to the Start menu.
#
#   powershell -ExecutionPolicy Bypass -File scripts\build-desktop.ps1 [-Into <folder>]
# -Into builds into <folder>\Budget Buddy instead (for example to test a build while another one runs).

param([string]$Into)

. "$PSScriptRoot\paths.ps1"

$Dist = if ($Into) { $Into } else { $LaunchDir }
$Out = Join-Path $Dist "Budget Buddy"
$Work = Join-Path $RepoRoot "build\desktop"

# Windows locks a running program's files, so building over it would fail half-way.
$running = Get-Process -Name "Budget Buddy", "Budget Buddy Home Base" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith($Out, [StringComparison]::OrdinalIgnoreCase) }
if ($running) {
    Write-Host "Budget Buddy is running from $Out. Close its window and choose Quit on its tray icon, then build again." -ForegroundColor Yellow
    exit 1
}

Install-Part $ServerDir "package" "the Home Base packaging tools"
Install-Part $DesktopDir "build" "the desktop app tools"

New-Item -ItemType Directory -Force $Work | Out-Null
& $DesktopPython -m budget_buddy_desktop.icon (Join-Path $Work "budget-buddy.ico")
if ($LASTEXITCODE -ne 0) { throw "Drawing the icon failed." }

function Invoke-PyInstaller($VenvPython, $Spec, $DistPath) {
    & $VenvPython -m PyInstaller --noconfirm --clean --log-level WARN --workpath $Work --distpath $DistPath $Spec
    if ($LASTEXITCODE -ne 0) { throw "Building $Spec failed." }
}

Write-Host "Building Budget Buddy.exe and the Home Base (a few minutes)..."
Invoke-PyInstaller $DesktopPython (Join-Path $DesktopDir "packaging\desktop.spec") $Dist
Invoke-PyInstaller $Python (Join-Path $ServerDir "packaging\home-base.spec") $Out
Copy-Item (Join-Path $DesktopDir "packaging\THIRD-PARTY-NOTICES.txt") $Out

Write-Host ""
Write-Host "Built: $(Join-Path $Out 'Budget Buddy.exe')" -ForegroundColor Green
Write-Host "Try it from there, or double-click 'Install desktop app' in the launch folder."
