# Use Budget Buddy on another computer

Budget Buddy runs on one computer at home: the **Budget Buddy computer**. You can also open it in a web browser
on another computer in your house, like a laptop, once you've connected that computer with a one-time code.

> **Only on a home network you trust.** Phones sync with extra encryption, but a web browser on another computer
> talks to Budget Buddy without it. Someone who can watch your Wi-Fi traffic could see your pages. Use a strong
> Wi-Fi password, don't do this on public or shared Wi-Fi, and remove computers you no longer use.

## Connect a computer (once)

On the **Budget Buddy computer**:

1. Open Budget Buddy and click **Devices** at the top, then the **Other computers** tab.
2. Click **Allow another computer**. Budget Buddy shows an address, like `http://192.168.1.20:8765/`, and a code,
   like `ABCD-EFGH`. The code works once, for 10 minutes.

On the **other computer**:

3. Open a web browser (Edge, Chrome, Firefox or Safari) and type the address exactly as shown.
4. Type the code and a name for this computer, like "Kitchen laptop", then click **Connect**.
5. The page reloads and shows your budget. Bookmark the address so you can come back to it.

The Budget Buddy computer shows **New computer connected**. If Windows asks whether to let Python or Budget Buddy
use the network, allow **Private networks** only (the same as for phones).

## What another computer can do

Everything on the dashboard: see your budget, add and change transactions, import bank files, taxes and so on.
It **can't** connect phones or other computers. That stays on the Budget Buddy computer, so a lost laptop can't
let anything else in.

Budget Buddy has to be running on the Budget Buddy computer for the other computer to use it.

## Remove a computer

On the Budget Buddy computer: **Devices**, then **Other computers**, then **Remove** next to it. It stops working
right away. To use it again, connect it again with a new code.

## Something went wrong?

| What you see | What to do |
| --- | --- |
| The page won't load on the other computer | Check that both computers are on the same home network and Budget Buddy is running. Type the address exactly as shown, including the `:8765` part. Check that Windows Firewall allows Budget Buddy on **Private networks**. |
| "Budget Buddy only answers when it's opened as ..." | Use the number address shown on the Budget Buddy computer, not the computer's name. |
| "That code isn't right." | Check the code on the Budget Buddy computer. Upper or lower case and the dash don't matter. |
| "That code has run out or was already used." | Click **Allow another computer** again for a new code. After five wrong tries a code stops working. |
| "This computer isn't connected to Budget Buddy yet." | Reload the page and enter a new code. This happens after the computer was removed. |
| "This can only be done on the computer where Budget Buddy is running." | Connecting phones and computers only works on the Budget Buddy computer. |
| The address changed | Your router may give the Budget Buddy computer a new address. Get a new address on the **Other computers** tab; the connection is kept. |
