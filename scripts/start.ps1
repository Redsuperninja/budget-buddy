# Start Budget Buddy for everyday use: sets itself up the first time, starts the Home Base, and opens
# the dashboard in your browser. Close this window (or press Ctrl+C) to stop Budget Buddy.
#
#   Double-click "Start Budget Buddy" in the launch folder, or run:
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1 [-NoBrowser]
#
# Uses your real data folder and port 8765 (or BUDGET_BUDDY_DATA_DIR / BUDGET_BUDDY_PORT if you set them).
# Testers with made-up data use start-test-server.ps1 instead.

param([switch]$NoBrowser)

. "$PSScriptRoot\paths.ps1"

$Port = if ($env:BUDGET_BUDDY_PORT) { $env:BUDGET_BUDDY_PORT } else { "8765" }
$Url = "http://127.0.0.1:$Port/"

function Test-Running {
    try {
        $r = Invoke-WebRequest -Uri "${Url}api/health" -UseBasicParsing -TimeoutSec 2
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Open-Dashboard {
    if (-not $NoBrowser) { Start-Process $Url }
}

$Host.UI.RawUI.WindowTitle = "Budget Buddy"
Write-Host "Budget Buddy" -ForegroundColor Cyan

if (Test-Running) {
    Write-Host "Budget Buddy is already running. Opening it in your browser: $Url" -ForegroundColor Green
    Open-Dashboard
    exit 0
}

Install-HomeBase

Write-Host "Starting... your data stays on this computer."
$server = Start-Process -FilePath $Python -ArgumentList "-m", "app" -WorkingDirectory $ServerDir -NoNewWindow -PassThru
try {
    $ready = $false
    for ($i = 0; $i -lt 60 -and -not $server.HasExited; $i++) {
        if (Test-Running) { $ready = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) {
        Write-Host "Budget Buddy didn't start. The messages above say why. If another program uses port $Port, close it or set BUDGET_BUDDY_PORT." -ForegroundColor Yellow
        exit 1
    }
    Write-Host ""
    Write-Host "Budget Buddy is running: $Url" -ForegroundColor Green
    Write-Host "Keep this window open while you use it. Close it, or press Ctrl+C, to stop."
    Write-Host ""
    Open-Dashboard
    $server.WaitForExit()
} finally {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -ErrorAction SilentlyContinue }
}
