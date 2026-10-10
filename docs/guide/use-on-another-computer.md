# Use Budget Buddy on another computer or your phone's browser

Budget Buddy runs on one computer at home: the **Budget Buddy computer**. You can also open it in a web browser
on another device in your house, like a laptop, a tablet or your phone, once you've connected it with a one-time
code. There's nothing to install: on a phone, the pages rearrange to fit the screen.

(The [phone app](connect-your-phone.md) is a separate option: it works away from home and takes receipt photos.
The web browser is the quickest way to use Budget Buddy on your phone at home.)

> **Only on a home network you trust.** Phones sync with extra encryption, but a web browser on another computer
> talks to Budget Buddy without it. Someone who can watch your Wi-Fi traffic could see your pages. Use a strong
> Wi-Fi password, don't do this on public or shared Wi-Fi, and remove devices you no longer use.

## Connect a computer or phone (once)

On the **Budget Buddy computer**:

1. Open Budget Buddy and click **Devices** at the top, then the **Other devices** tab.
2. Click **Allow another device**. Budget Buddy shows an address, like `http://192.168.1.20:8765/`, and a code,
   like `ABCD-EFGH`. The code works once, for 10 minutes.

On the **other computer or phone**:

3. Make sure it's on your home Wi-Fi. Open a web browser (Edge, Chrome, Firefox or Safari) and type the address
   exactly as shown.
4. Type the code and a name, like "Kitchen laptop" or "Sam's phone", then click **Connect**.
5. The page reloads and shows your budget. Bookmark the address so you can come back to it. On a phone, you can
   add it to your home screen: in Safari tap **Share**, then **Add to Home Screen**; in Chrome tap the **⋮** menu,
   then **Add to Home screen**.

The connection works from that device's network address for 90 days; after that, or if your router gives it
a new address, connect it again with a new code. The Budget Buddy computer shows **Connected**. If
Windows asks whether to let Python or Budget Buddy use the network, allow **Private networks** only (the same as
for phones).

## What another computer or phone can do

Everything on the dashboard: see your budget, add and change transactions, import bank files, taxes and so on.
It **can't** connect phones or other devices. That stays on the Budget Buddy computer, so a lost laptop can't
let anything else in.

Budget Buddy has to be running on the Budget Buddy computer for the other device to use it.

## Remove a computer or phone

On the Budget Buddy computer: **Devices**, then **Other devices**, then **Remove** next to it. It stops working
right away. To use it again, connect it again with a new code.

## Something went wrong?

| What you see | What to do |
| --- | --- |
| The page won't load on the other computer or phone | Check that both are on the same home Wi-Fi (on a phone, turn off mobile data for a moment if it keeps switching) and Budget Buddy is running. Type the address exactly as shown, including the `:8765` part. Check that Windows Firewall allows Budget Buddy on **Private networks**. |
| "Budget Buddy only answers when it's opened as ..." | Use the number address shown on the Budget Buddy computer, not the computer's name. |
| "That code isn't right, or it has run out." | Check the code on the Budget Buddy computer (upper or lower case and the dash don't matter), or click **Allow another device** for a new one. After five wrong tries a code stops working. |
| "This computer isn't connected to Budget Buddy yet." | Reload the page and enter a new code. This happens after the computer was removed, after 90 days, or when its network address changed. |
| "This can only be done on the computer where Budget Buddy is running." | Connecting phones and computers only works on the Budget Buddy computer. |
| The address changed | Your router may give the Budget Buddy computer a new address. Get the new one on the **Other devices** tab. |
