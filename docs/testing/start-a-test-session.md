# Start a test session

Each time you test, open three terminal windows in the Budget Buddy folder (see
[Set up for testing](set-up-for-testing.md), step 2) and run one command in each. Keep them open while you're
testing. On Windows, type `py` instead of `python3` in every command.

## Window 1: Start the test Budget Buddy

```
python3 scripts/testing/start_test_server.py
```

Leave this window open. The test version uses its own data folder (it shows where) on its own port (8766),
completely separate from any real Budget Buddy data.

## Window 2: Add demo data (first time only)

```
python3 scripts/testing/load_demo_data.py
```

This adds three months of made-up accounts, spending, paychecks, donations and stocks. Skip this if you already
loaded demo data.

To try importing a bank file, run `python3 scripts/testing/import_csv.py` here too: it shows a sample statement
and asks before importing it.

## Window 3: Start your phone app

```
python3 scripts/testing/start_phone_app.py
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
3. Click **Show pairing code** (or in window 2, run `python3 scripts/testing/pair_phone.py` to get a code in the
   window)
4. Scan the code on your phone. It works once, for 10 minutes
5. The page says **New phone paired** when it worked
6. The phone should say **Connected to …**

## When you're done testing

Press Ctrl+C in each window to stop. This also stops the phone app's test server, which otherwise stays reachable
on your home Wi-Fi.

## Start over with fresh demo data

Stop window 1 (Ctrl+C), then run:

```
python3 scripts/testing/start_test_server.py --reset
```

This clears only the test data folder. Your phone will need to connect again.

## Something went wrong?

**The phone says it can't reach the computer, or Expo Go can't load the app**

- Check that both are on the same home Wi-Fi (not a guest network)
- On Windows, make sure the Wi-Fi is set to Private (not Public), and that you added the firewall rule from the
  setup page
- Don't use "Allow an app" to allow Python or Node.js — that opens every Python or Node program, not just Budget
  Buddy

**The test Home Base isn't running**

Start window 1 and leave it open.

**Budget Buddy isn't set up on this computer yet**

Run `python3 scripts/testing/set_up.py` from the [setup page](set-up-for-testing.md) first.

**The QR code won't scan**

Use the bigger picture window, or make the terminal window larger.
