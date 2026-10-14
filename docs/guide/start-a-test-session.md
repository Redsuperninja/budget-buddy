# Start a test session

Each time you test, open three PowerShell windows and run one script in each. Keep them open while you're testing.

## Window 1: Start the test Budget Buddy

Run this command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\testing\start-test-server.ps1
```

Leave this window open. The test version uses its own folder (`%LOCALAPPDATA%\BudgetBuddy-Test`) on its own port (8766), completely separate from any real Budget Buddy data.

## Window 2: Add demo data (first time only)

Run this command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\testing\load-demo-data.ps1
```

This adds three months of made-up accounts, spending, paychecks, donations and stocks. Skip this if you already loaded demo data.

## Window 3: Start your phone app

Run this command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\testing\start-phone-app.ps1
```

You'll see a QR code in the window.

## On your phone

Scan the QR code:
- **iPhone:** use the Camera app
- **Android:** use Expo Go

Budget Buddy opens inside Expo Go.

## Pair your phone to the computer

1. On your phone: **Settings → Connect**
2. On your computer, open http://127.0.0.1:8766/ in your browser
3. Click **Show pairing code** (or in window 2, run `powershell -ExecutionPolicy Bypass -File scripts\testing\pair-phone.ps1` to get a code in the window)
4. Scan the code on your phone. It works once, for 10 minutes
5. The page says **New phone paired** when it worked
6. The phone should say **Connected to …**

## When you're done testing

Press Ctrl+C in each window to stop. This also stops the phone app's test server, which otherwise stays reachable on your home Wi-Fi.

## Start over with fresh demo data

Run this command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\testing\start-test-server.ps1 -Reset
```

This clears only the test data folder. Your phone will need to connect again.

## Something went wrong?

**The phone says it can't reach the computer, or Expo Go can't load the app**

- Check that both are on the same home Wi-Fi (not a guest network)
- Make sure the Wi-Fi is set to Private (not Public)
- Check that you added the firewall rule from the setup page
- Don't use "Allow an app" to allow Python or Node.js — that opens every Python or Node program, not just Budget Buddy

**The test Home Base isn't running**

Start window 1 and leave it open.

**Budget Buddy isn't set up on this computer yet**

Run `scripts\testing\setup.ps1` from the setup page first.

**The QR code won't scan**

Use the bigger picture window, or make the PowerShell window larger.
