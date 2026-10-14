# Open every dashboard page in a headless browser against a throwaway Home Base with demo data, and fail on a
# script error, a file that didn't load, an error on the page, or an empty page. Catches what file-reading tests
# can't, like a screen that breaks only when it runs. Needs Microsoft Edge or Google Chrome, and Node 22+.
#
#   powershell -ExecutionPolicy Bypass -File scripts\dev\check-pages.ps1
#
# Your real data and your own test data are never touched: everything lives in a new temporary folder (with the
# encryption key in memory only) that is deleted afterwards. Uses the test port, 8766, so stop a test Home Base first.

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\paths.ps1"

$Browser = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Browser) { Write-Host "Needs Microsoft Edge or Google Chrome." -ForegroundColor Yellow; exit 1 }
if (-not (Test-Path $Python)) { Write-Host "Set up the Home Base first (docs/dev/testing.md)." -ForegroundColor Yellow; exit 1 }
foreach ($port in 8766, 9333) {  # the test Home Base, and the browser's DevTools port (check-pages.mjs)
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "Something is already using port $port. Stop it and try again." -ForegroundColor Yellow
        exit 1
    }
}

# True if process $Id was started by process $Ancestor, directly or a few steps down (the venv's python.exe
# starts the real one).
function Test-StartedBy($Id, $Ancestor) {
    for ($step = 0; $step -lt 4 -and $Id; $step++) {
        $Id = (Get-CimInstance Win32_Process -Filter "ProcessId=$Id" -ErrorAction SilentlyContinue).ParentProcessId
        if ($Id -eq $Ancestor) { return $true }
    }
    return $false
}

$Run = Join-Path ([IO.Path]::GetTempPath()) "budget-buddy-check-pages-$PID"
New-Item -ItemType Directory -Force $Run | Out-Null
# The test scripts keep their data under LOCALAPPDATA; point it at the temporary folder for this run only.
$Saved = @{}
$Settings = @{ LOCALAPPDATA = $Run; BUDGET_BUDDY_KEY_STORE = "memory"; BUDGET_BUDDY_INSECURE_TEST_KEYSTORE = "1" }
foreach ($name in $Settings.Keys) {
    $Saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    [Environment]::SetEnvironmentVariable($name, $Settings[$name], "Process")
}
$server = $null
$exitCode = 1
try {
    $server = Start-Process powershell -PassThru -WindowStyle Hidden -RedirectStandardOutput "$Run\server.log" `
        -RedirectStandardError "$Run\server-errors.log" `
        -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$RepoRoot\scripts\testing\start-test-server.ps1"
    $up = $false
    for ($i = 0; $i -lt 60 -and -not $up; $i++) {
        try { Invoke-RestMethod "http://127.0.0.1:8766/api/health" -TimeoutSec 2 | Out-Null; $up = $true } catch { Start-Sleep 1 }
    }
    if (-not $up) { throw "The test Home Base didn't start; see $Run\server-errors.log." }
    & powershell -NoProfile -ExecutionPolicy Bypass -File "$RepoRoot\scripts\testing\load-demo-data.ps1" | Out-Null
    if ($LASTEXITCODE) { throw "Loading the demo data failed." }
    & node "$PSScriptRoot\check-pages.mjs" $Browser "http://127.0.0.1:8766" "$Run\browser"
    $exitCode = $LASTEXITCODE
} finally {
    # Stop only what this run started: the Home Base its start-test-server.ps1 started, and browsers using this
    # run's own folder.
    if ($server) {
        Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue |
            Where-Object { Test-StartedBy $_.OwningProcess $server.Id } |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
    Get-CimInstance Win32_Process -Filter "Name='msedge.exe' or Name='chrome.exe'" |
        Where-Object { $_.CommandLine -like "*$Run\*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    foreach ($name in $Settings.Keys) { [Environment]::SetEnvironmentVariable($name, $Saved[$name], "Process") }
    Start-Sleep 1
    Remove-Item -Recurse -Force $Run -ErrorAction SilentlyContinue
}
exit $exitCode
