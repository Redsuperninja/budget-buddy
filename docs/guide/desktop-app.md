# The desktop app

Budget Buddy can run as a normal Windows app with its own window: no web browser and no Python needed. It can
also wait quietly in the corner of your screen (the tray, next to the clock) from the moment Windows starts.

## Get it

1. Open the Budget Buddy folder, then the **launch** folder.
2. Double-click **Build desktop app** and wait a few minutes until it says **Built**. (Someone may have done this
   for you already.)
3. Double-click **Install desktop app**. It adds **Budget Buddy** to your Start menu and your desktop.

## Use it

Open **Budget Buddy** from the Start menu or the desktop. A small blue **B** icon appears in the tray, and the
Budget Buddy window opens a second or two later. Everything works as in the browser, including **Settings** (the simple view or
All tools, and light, dark, or match your computer), downloading the tax summary, and printing.

When you close the window, Budget Buddy stops and your data is saved. The tray icon stays, using almost nothing,
so you can open it again with a double-click.

## Ready when Windows starts

Right-click the tray icon and tick **Start with Windows**. From then on, the tray icon appears when you sign in,
but Budget Buddy itself doesn't start until you open it. To turn this off, untick it (or switch it off under
**Startup apps** in Windows Settings).

## Your phone

Your phone can only sync while the Budget Buddy window is open. The tray icon's menu says which: **Running:
phones can sync now**, or **Resting: open it to let phones sync**.

## Something went wrong?

- **Windows says it protected your PC.** The app isn't signed yet. Choose **More info**, then **Run anyway**.
- **"Budget Buddy couldn't start."** The message says why. If it mentions a port, another program is using it:
  restart the computer and try again.
- **"Budget Buddy is already open."** Look for its window on the taskbar.
- **Budget Buddy is already running from the launch folder.** That's fine: the app checks it's really Budget
  Buddy and opens it. Closing the app's window leaves it running; close its own window to stop it.
- **"Something else is using port 8765."** Another program is using Budget Buddy's port, so the app won't show
  it (it could be pretending to be Budget Buddy). Close that program, or restart the computer.
- **The page stays on "Loading Budget Buddy..."** Close every Budget Buddy window, including the tray icon's
  **Quit**, and start it again. This can happen right after an update.
- **Install says Budget Buddy is running.** Close the window, right-click the tray icon, choose **Quit**, then
  install again.
