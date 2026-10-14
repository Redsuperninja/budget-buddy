# Start the phone app for testing with Expo Go.
# Put the Expo Go app on your phone (App Store / Google Play), be on the same Wi-Fi as this computer,
# then scan the QR code this window shows. Press Ctrl+C to stop.

. "$PSScriptRoot\test-settings.ps1"

if (-not (Test-Path (Join-Path $MobileDir "node_modules"))) {
    Write-Host "The phone app tools aren't installed yet. Run scripts\testing\setup.ps1 first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting the phone app. Scan the QR code below with:" -ForegroundColor Cyan
Write-Host "  iPhone:  the Camera app      Android:  the Expo Go app"
Write-Host ""
Push-Location $MobileDir
try { npx expo start --lan } finally { Pop-Location }
