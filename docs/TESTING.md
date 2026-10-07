# Testing Budget Buddy (early preview)

Thanks for helping test! This is an **early preview**. Use only the made-up demo data, never your
real bank details. Everything here runs on your own computer and phone.

## What you can try today

| Part | Ready to try | Not built yet |
| --- | --- | --- |
| Computer (Home Base) | Accounts, transactions, categories and budgets, monthly summary, bank CSV import, paychecks, receipts, donations, stocks, connecting a phone. All through the **Budget Buddy dashboard**, a normal web page at <http://127.0.0.1:8766/> on the computer. | Editing or deleting most items from the page (add and view work; ask us if you need to fix something) |
| Phone app | Connecting to your computer, the Home and Taxes screens | Showing your real data (it shows **sample data** until sync, #15), receipt photos (#20), the Sync button and reminders (#21) |

## Before you start (once)

You need a Windows computer and a phone on the **same home Wi-Fi**.

1. Install **Python 3.12 or newer** from <https://www.python.org/downloads/>. Tick **"Add python.exe to PATH"**.
2. Install **Node.js LTS** from <https://nodejs.org/>.
3. On your phone, install **Expo Go** from the App Store or Google Play.
4. Open **PowerShell** in the Budget Buddy folder and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
   ```

   You'll see "All set" when it's done. It takes a few minutes the first time.

## Letting your phone reach the computer (once)

The phone talks to this computer over your home Wi-Fi, so Windows needs to let two ports in: **8766**
(the test Home Base) and **8081** (the phone app's test server).

1. Make sure Windows treats your home Wi-Fi as **Private**: *Settings → Network & internet → Wi-Fi →* your
   network *→ Network profile type → Private network*. Never do this for café or other public Wi-Fi.
2. Open **PowerShell as administrator** (right-click PowerShell → *Run as administrator*) and run:

   ```powershell
   New-NetFirewallRule -DisplayName "Budget Buddy test" -Direction Inbound -Protocol TCP -LocalPort 8766,8081 -Profile Private -Action Allow
   ```

3. If Windows later pops up asking whether Python or Node.js may use networks, choose **Cancel**. The rule above
   already covers what's needed, and never tick **Public**.

When you're done testing for good, remove the rule:

```powershell
Remove-NetFirewallRule -DisplayName "Budget Buddy test"
```

## Each time you test

Open three PowerShell windows in the Budget Buddy folder.

**Window 1: start the test Home Base**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-test-server.ps1
```

Leave it open. The test Home Base keeps its data in its own folder (`%LOCALAPPDATA%\BudgetBuddy-Test`)
on its own port (8766), completely apart from any real Budget Buddy data.

**Window 2: add demo data (first time only)**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\load-demo-data.ps1
```

This adds three months of made-up accounts, spending, paychecks, donations and stocks.

**Window 3: start the phone app**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-phone-app.ps1
```

Scan the QR code it shows: on iPhone with the **Camera** app, on Android with **Expo Go**.
Budget Buddy opens inside Expo Go.

**Connect the phone to the computer**

1. On the phone: **Settings → Connect**.
2. On the computer, open <http://127.0.0.1:8766/> in your browser, click **Connect phone**, then **Show pairing code**.
   (Alternative: in window 2 run `powershell -ExecutionPolicy Bypass -File scripts\pair-phone.ps1` for a code in the window.)
3. Scan the code on the screen. It works once, for 10 minutes. The page says **New phone paired** when it worked.
4. The phone should say **"Connected to …"**.

## Things to try (checklist)

Open <http://127.0.0.1:8766/> on the computer and use the tabs along the top (Home, Accounts, Transactions, and so on).

- [ ] **Monthly summary:** on **Home**, pick this month. Do income and spending look right? Is the "not sorted yet" money clear?
- [ ] **Categories:** add one, rename it, give it a budget. Try a name that already exists.
- [ ] **Transactions:** add a purchase (choose "Money out", amount `12.34`). Add a refund.
- [ ] **CSV import:** on **Import bank file**, choose `scripts\sample-bank-statement.csv`, check the preview,
  then import. Do it again: rows already there should be skipped. (`scripts\import-csv.ps1` still works too.)
- [ ] **Paychecks:** add one whose numbers don't add up. Is the message clear?
- [ ] **Donations:** look at the year summary for this year. Does the "proof to keep" list make sense?
- [ ] **Stocks:** look at the gains for this year. Add a sale of more shares than you own.
- [ ] **Phone:** connect, then disconnect and connect again. Try scanning an old or used code.
- [ ] **Messages:** were any error messages confusing or too technical? Note the exact words.

## Reporting what you find

Open an issue on GitHub with the **"User testing feedback"** template, or write down:

1. What you were trying to do.
2. What you expected to happen.
3. What happened instead (the exact message, or a screenshot).

Please don't include real financial information in reports.

## Starting over

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-test-server.ps1 -Reset
```

This clears **only** the test data folder. Your phone will need to connect again.

## Something went wrong?

- **"Budget Buddy isn't set up on this computer yet":** run `scripts\setup.ps1` first.
- **"The test Home Base isn't running":** start window 1 and leave it open.
- **The phone says it can't reach the computer, or Expo Go can't load the app:** check both are on the same
  Wi-Fi (not guest Wi-Fi), that the Wi-Fi is set to **Private**, and that you added the firewall rule in
  "Letting your phone reach the computer". Don't use *Allow an app* to tick Python or Node.js: that opens every
  Python or Node program, not just Budget Buddy.
- **When you finish a session:** press Ctrl+C in each window. That stops the phone app's test server too, which
  otherwise stays reachable on your home Wi-Fi.
- **The QR code won't scan:** use the bigger picture window, or make the PowerShell window larger.
- **"Running scripts is disabled on this system":** use the `powershell -ExecutionPolicy Bypass -File ...` form shown above.
