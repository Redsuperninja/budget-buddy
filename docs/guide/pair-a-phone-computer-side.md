# Pair a phone: on your computer

Pairing connects your phone to Budget Buddy on this computer. You do it once per phone. Your
computer and phone need to be on the same home Wi-Fi.

## Start pairing

1. Open Budget Buddy on your computer and ask to pair a phone ("Pair a phone").
2. Budget Buddy shows a one-time code as a QR code. It works **once** and runs out after
   **10 minutes**. If it runs out, or you ask again, the old code stops working and you get a new one.
3. On your phone, open Budget Buddy and scan the QR code.
4. The first time, Windows may ask whether to let Python use the network. Choose
   **Private networks** only. Leave **Public networks** unticked.

Anyone who can see the QR code could try to pair with it, so don't leave it on screen or share a
photo of it. Once your phone is paired, the code is used up.

## "Show code as text"

If the camera can't scan the QR code, choose **Show code as text**. You'll see one line of text
starting with `{"v":1`. Copy it and paste it into your phone's Budget Buddy where it asks for the
code. Treat this text like the QR code: it's a one-time key, so don't post it anywhere.

## See and remove connected phones

Budget Buddy lists the phones that are connected: their name, when they were paired, and when
they last synced. When a new phone pairs, check that you recognise it.

If you see a phone you don't recognise, or you didn't just pair one, click **Remove**. A removed
phone stops working right away, and its access key is deleted from your computer. It stays in the
list marked as removed, so you can see what happened. To use that phone again, pair it again.

## Something went wrong?

- **"Budget Buddy can't find your home network."** This computer isn't on a home network.
  Connect it to your home Wi-Fi and try again. If it is connected but still can't find it, your
  computer may have more than one network connection. Ask whoever set up Budget Buddy to set
  `BUDGET_BUDDY_LAN_IP` to this computer's home address (it looks like `192.168.1.20`).
- **"Budget Buddy couldn't open its home-network connection."** Check you're on home Wi-Fi and
  that no other program is using Budget Buddy's port (8765), then try again.
- **"Budget Buddy was set to answer only on this computer."** Someone set `BUDGET_BUDDY_HOST` to
  `127.0.0.1`. Remove that setting and restart Budget Buddy.
- **The phone says the code has expired.** Ask for a new code on your computer and scan again.
- **The phone says "Too many tries".** Wait a minute and scan again.
- **The phone says the clock is wrong.** Turn on automatic date and time on both your phone and
  your computer.
- **The phone can't reach your computer.** Make sure both are on the same home Wi-Fi (not a guest
  network) and that Budget Buddy is running on your computer.
