# Show a pairing QR code from the TEST Home Base so a phone can connect.
# On the phone: Budget Buddy > Settings > Connect, then scan the code. It works once, for 10 minutes.

. "$PSScriptRoot\test-settings.ps1"
Assert-SetUp
& $Python (Join-Path $PSScriptRoot "pair_phone.py") --port $TestPort
exit $LASTEXITCODE
