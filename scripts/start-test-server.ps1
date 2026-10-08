# Start a TEST Home Base with its own data folder and port, kept apart from any real data.
# Leave this window open while testing; press Ctrl+C to stop.
#
#   powershell -ExecutionPolicy Bypass -File scripts\start-test-server.ps1          keep last time's test data
#   powershell -ExecutionPolicy Bypass -File scripts\start-test-server.ps1 -Reset   start over, empty

param([switch]$Reset)

. "$PSScriptRoot\test-settings.ps1"
Assert-SetUp

$Marker = Join-Path $TestDataDir ".budget-buddy-test-folder"

if ($Reset -and (Test-Path $TestDataDir)) {
    # Only ever a folder this script made (it has the marker). Paired test phones will need to connect again.
    if (-not (Test-Path $Marker)) {
        Write-Host "Not clearing $TestDataDir`: it wasn't made by this script, so it may not be test data." -ForegroundColor Yellow
        exit 1
    }
    Remove-Item -Recurse -Force $TestDataDir
    Write-Host "Test data cleared." -ForegroundColor Yellow
}

New-Item -ItemType Directory -Force $TestDataDir | Out-Null
if (-not (Test-Path $Marker)) {
    Set-Content -Path $Marker -Encoding ASCII -Value "Budget Buddy TEST data folder. Made-up data only. Safe to delete."
}

# Set the test settings for this run only, and put the window's old values back afterwards, so a
# real Home Base started later from this same window doesn't pick them up.
$Names = "BUDGET_BUDDY_DATA_DIR", "BUDGET_BUDDY_PORT", "BUDGET_BUDDY_DEV_MODE"
$Saved = @{}
foreach ($name in $Names) { $Saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }

Write-Host ""
Write-Host "Budget Buddy TEST Home Base" -ForegroundColor Cyan
Write-Host "  Test data folder: $TestDataDir"
Write-Host "  Open Budget Buddy:  http://127.0.0.1:$TestPort/   (type this into your browser)" -ForegroundColor Green
Write-Host "  Check it's running: http://127.0.0.1:$TestPort/api/health"
Write-Host "  API explorer:       http://127.0.0.1:$TestPort/docs"
Write-Host ""
Write-Host "If Windows asks whether to allow Python on networks, tick 'Private networks' only, never Public." -ForegroundColor Yellow
Write-Host "See 'Step 3: Add a firewall rule' in docs\guide\set-up-for-testing.md. Press Ctrl+C to stop."
Write-Host ""

Push-Location $ServerDir
try {
    $env:BUDGET_BUDDY_DATA_DIR = $TestDataDir
    $env:BUDGET_BUDDY_PORT = "$TestPort"
    $env:BUDGET_BUDDY_DEV_MODE = "true"   # turns on the API explorer page for testers
    & $Python -m app
} finally {
    foreach ($name in $Names) { [Environment]::SetEnvironmentVariable($name, $Saved[$name], "Process") }
    Pop-Location
}
