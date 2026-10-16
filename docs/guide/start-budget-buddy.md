# Start Budget Buddy

For everyday use with your own money, on Windows, a Mac or Linux. (Trying it out with made-up data? See
[Start a test session](../testing/start-a-test-session.md) instead.)

## The first time

1. Install **Python 3.12 or newer** from <https://www.python.org/downloads/>. On Windows, tick **Add python.exe
   to PATH** on the first installer screen. On Linux, your system's software store or package manager has it.
2. Open the Budget Buddy folder, then the **launch** folder, and start it:
   - **Windows:** double-click **Start Budget Buddy**.
   - **Mac:** double-click **Start Budget Buddy.command**. The first time, your Mac may say it can't check the
     file: right-click it, choose **Open**, then **Open** again.
   - **Linux:** open a terminal in the Budget Buddy folder and run `./launch/start-budget-buddy.sh`.
3. A window opens and sets things up. This takes a few minutes the first time only.
4. When it says **Budget Buddy is running**, your browser opens the dashboard.

## Every time after that

Start it the same way as in step 2. Your browser opens the dashboard in a few seconds.

If Budget Buddy is already running, starting it again just opens the dashboard.

## Stop it

Close the Budget Buddy window (or press Ctrl+C in it). Your data is saved as you go, so closing it is safe.

## Keep it handy

- **Windows:** right-click **Start Budget Buddy**, choose **Show more options**, then **Send to** and **Desktop
  (create shortcut)**. Or use [the desktop app](desktop-app.md): its own window, a Start menu entry and a tray
  icon.
- **Mac:** right-click **Start Budget Buddy.command**, choose **Make Alias**, and drag the alias to your
  desktop.

## Something went wrong?

- **"Budget Buddy needs Python 3.12 or newer."** Install it (step 1 above), then start again.
- **"Budget Buddy didn't start."** Read the lines just above it. Another program may be using the same
  address; restart the computer and try again.
- **On Linux, "install python3-venv first".** Run the command it shows (it asks for your password), then start
  again.
- **Windows asks whether to allow Python on networks.** Choose **Private networks** only, never Public. It's
  needed only when you connect your phone.
- **The window closes straight away (Windows).** It stays open when something goes wrong, so this usually means
  Windows blocked it. Open the Budget Buddy folder, type `cmd` in the address bar, press Enter, and type
  `py scripts\start.py` to see the message.
