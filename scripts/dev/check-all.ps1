# Run every part's checks, the same ones CI runs, and say which passed. Use it before pushing or merging,
# especially for a change in one part that others depend on (a route, the snapshot, the desktop handshake).
#
#   powershell -ExecutionPolicy Bypass -File scripts\dev\check-all.ps1
#
# Each part must be set up once first (docs/dev/testing.md); a part that isn't is reported, not skipped quietly.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$results = [ordered]@{}

function Check($Name, $Dir, $Ready, [scriptblock[]]$Steps) {
    if (-not (Test-Path (Join-Path $Root "$Dir\$Ready"))) {
        $results[$Name] = "NOT SET UP (see docs/dev/testing.md)"
        return
    }
    Push-Location (Join-Path $Root $Dir)
    try {
        foreach ($step in $Steps) {
            & $step
            if ($LASTEXITCODE) { $results[$Name] = "FAILED: $step"; return }
        }
        $results[$Name] = "passed"
    } finally {
        Pop-Location
    }
}

Check "Server" "server" ".venv\Scripts\pytest.exe" @(
    { .venv\Scripts\ruff check . }, { .venv\Scripts\ruff format --check . }, { .venv\Scripts\pytest -q }
)
Check "Dashboard" "dashboard" "package.json" @({ node --test })
Check "Phone" "mobile" "node_modules" @({ npx tsc --noEmit }, { npm test -- --silent })
Check "Desktop" "desktop" ".venv\Scripts\pytest.exe" @(
    { .venv\Scripts\ruff check . }, { .venv\Scripts\ruff format --check . }, { .venv\Scripts\pytest -q }
)

Write-Host ""
foreach ($part in $results.Keys) {
    $color = if ($results[$part] -eq "passed") { "Green" } else { "Yellow" }
    Write-Host ("{0,-10} {1}" -f $part, $results[$part]) -ForegroundColor $color
}
if ($results.Values | Where-Object { $_ -ne "passed" }) { exit 1 }
