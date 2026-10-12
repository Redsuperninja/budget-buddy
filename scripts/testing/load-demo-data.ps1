# Fill the TEST Home Base with made-up demo data (accounts, three months of spending, paychecks,
# donations, stocks). Start scripts\testing\start-test-server.ps1 in another window first.

. "$PSScriptRoot\test-settings.ps1"
Assert-SetUp
& $Python (Join-Path $PSScriptRoot "demo_data.py") --port $TestPort
exit $LASTEXITCODE
