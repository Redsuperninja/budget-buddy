# Set up for testing

You need a computer (Windows, Mac or Linux) and a phone on the same home Wi-Fi. This setup takes a few minutes the
first time.

## Step 1: Install required software

1. Install **Python 3.12 or newer** from https://www.python.org/downloads/
   - On Windows, make sure to tick "Add python.exe to PATH"
   - On Linux, your package manager has it; on Ubuntu or Debian also install `python3-venv`
2. Install **Node.js LTS** from https://nodejs.org/
3. On your phone, install **Expo Go** from the App Store (iPhone) or Google Play (Android)

## Step 2: Run the setup script

1. Open a terminal in the Budget Buddy folder:
   - **Windows:** open the folder, type `cmd` in the address bar and press Enter
   - **Mac:** open Terminal (in Applications, Utilities), type `cd ` with a space after it, drag the Budget Buddy
     folder into the window, and press Enter
   - **Linux:** right-click in the folder and choose **Open in Terminal**
2. Run this command (on Windows, type `py` instead of `python3`; the same goes for every command in these guides):
   ```
   python3 scripts/testing/set_up.py
   ```
   You'll see "All set" when it's done

## Step 3: Let your phone reach the computer

Your phone needs to reach your computer over Wi-Fi on two ports: **8766** (the test Budget Buddy) and **8081** (the
phone app's test server).

### Windows: add a firewall rule

1. Make sure Windows treats your home Wi-Fi as **Private**:
   - Go to Settings → Network & internet → Wi-Fi → your network → Network profile type
   - Choose Private network (never do this for café or other public Wi-Fi)
2. Open **PowerShell as administrator** (right-click PowerShell → Run as administrator)
3. Run this command:
   ```powershell
   New-NetFirewallRule -DisplayName "Budget Buddy test" -Direction Inbound -Protocol TCP -LocalPort 8766,8081 -Profile Private -Action Allow
   ```

When you start testing, Windows may still ask whether Python or Node.js may use networks. Choose **Private
networks only** and leave Public networks unticked, or choose **Cancel**: the rule already covers what's needed.

### Mac

Nothing to set up now. When you start testing, your Mac may ask whether Python and Node accept incoming network
connections: choose **Allow**.

### Linux

Most desktops don't block these ports. If you turned on a firewall (`sudo ufw status` says "active"), allow your
home network only:

```
sudo ufw allow from 192.168.0.0/16 to any port 8766,8081 proto tcp
```

## When you're done testing

- **Windows:** remove the firewall rule, in PowerShell as administrator:
  ```powershell
  Remove-NetFirewallRule -DisplayName "Budget Buddy test"
  ```
- **Linux:** if you added the ufw rule: `sudo ufw delete allow from 192.168.0.0/16 to any port 8766,8081 proto tcp`

## Something went wrong?

**"Budget Buddy needs Python 3.12 or newer", or `python3` / `py` isn't found**

Install Python (step 1). On Windows, run the installer again and tick "Add python.exe to PATH".

**"Node.js isn't installed"**

Install Node.js LTS (step 1), close the terminal, open a new one and run the setup again.

**"install python3-venv first" (Linux)**

Run the command it shows (it asks for your password), then run the setup again.
