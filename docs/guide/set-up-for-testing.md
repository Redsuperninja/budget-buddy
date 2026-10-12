# Set up for testing

You need a Windows computer and a phone on the same home Wi-Fi. This setup takes a few minutes the first time.

## Step 1: Install required software

1. Install **Python 3.12 or newer** from https://www.python.org/downloads/
   - Make sure to tick "Add python.exe to PATH"
2. Install **Node.js LTS** from https://nodejs.org/
3. On your phone, install **Expo Go** from the App Store (iPhone) or Google Play (Android)

## Step 2: Run the setup script

1. Open **PowerShell** (search for PowerShell in Windows)
2. Navigate to the Budget Buddy folder
3. Run this command:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\testing\setup.ps1
   ```
   You'll see "All set" when it's done

## Step 3: Add a firewall rule (Windows will ask about this)

Your phone needs to reach your computer over Wi-Fi, so Windows needs to allow two ports: **8766** (the test Budget Buddy) and **8081** (the phone app's test server).

1. Make sure Windows treats your home Wi-Fi as **Private**: 
   - Go to Settings → Network & internet → Wi-Fi → your network → Network profile type
   - Choose Private network (never do this for café or other public Wi-Fi)

2. Open **PowerShell as administrator** (right-click PowerShell → Run as administrator)

3. Run this command:
   ```powershell
   New-NetFirewallRule -DisplayName "Budget Buddy test" -Direction Inbound -Protocol TCP -LocalPort 8766,8081 -Profile Private -Action Allow
   ```

## Windows firewall prompt when you start testing

When you start testing, Windows may ask whether Python or Node.js may use networks. 

- For normal testing, choose **Private networks only**. Leave Public networks unticked.
- If you already added the firewall rule above, you can choose **Cancel** instead; the rule already covers what's needed.

## When you're done testing

Remove the firewall rule:

```powershell
Remove-NetFirewallRule -DisplayName "Budget Buddy test"
```

## Something went wrong?

**"Running scripts is disabled on this system"**

Use the `powershell -ExecutionPolicy Bypass -File ...` form shown above.

**The setup script failed**

Make sure you've installed Python and Node.js, and that Python was added to PATH (the setup.ps1 command should find it).
