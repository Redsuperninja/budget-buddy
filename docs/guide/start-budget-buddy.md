# Start Budget Buddy

For everyday use with your own money. (Trying it out with made-up data? See
[Start a test session](start-a-test-session.md) instead.)

## The first time

1. Install **Python 3.12 or newer** from <https://www.python.org/downloads/>. On the first installer screen,
   tick **Add python.exe to PATH**.
2. Open the Budget Buddy folder, then the **launch** folder, and double-click **Start Budget Buddy**.
3. A window opens and sets things up. This takes a few minutes the first time only.
4. When it says **Budget Buddy is running**, your browser opens the dashboard.

## Every time after that

Double-click **Start Budget Buddy**. Your browser opens the dashboard in a few seconds.

If Budget Buddy is already running, double-clicking again just opens the dashboard.

## Stop it

Close the Budget Buddy window. Your data is saved as you go, so closing it is safe.

## Keep it handy

Right-click **Start Budget Buddy**, choose **Show more options**, then **Send to** and **Desktop (create
shortcut)**. Or use [the desktop app](desktop-app.md): its own window, a Start menu entry and a tray icon.

## Something went wrong?

- **"Budget Buddy needs Python 3.12 or newer."** Install it (step 1 above), then double-click again.
- **"Budget Buddy didn't start."** Read the lines just above it. Another program may be using the same
  address; restart the computer and try again.
- **Windows asks whether to allow Python on networks.** Choose **Private networks** only, never Public. It's
  needed only when you connect your phone.
- **The window closes straight away.** It stays open when something goes wrong, so this usually means
  Windows blocked it. Open the Budget Buddy folder, type `powershell` in the address bar, press Enter, and
  run `powershell -ExecutionPolicy Bypass -File scripts\start.ps1` to see the message.
