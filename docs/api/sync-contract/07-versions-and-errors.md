Part of the [Sync API contract, v1](../sync-contract.md). Conventions and key names are in §1 there.

## 7. Versioning and plain-English errors

### 7.1 Versions

- **Contract version** (`1`): in the QR `v`, `/api/health` `contract`, every inner request `contract`, and the
  snapshot. **Envelope version** (`v` in the envelope, `1`): the crypto format only.
- Adding optional fields, new endpoints, or new enum values that receivers can ignore does **not** bump the
  contract. Removing/renaming fields, changing meaning or crypto bumps it.
- When v2 exists, the server keeps accepting v1 for at least one release so an older phone gets a clear
  `update_needed`.

### 7.2 What the phone says and does

The phone maps each code to its own message (the server's `message` is a fallback for unknown codes). Each
message says what happened and what to do.

**"Needs attention" state.** For `not_paired`, `device_revoked` and `decrypt_failed` the phone sets a
*needs attention* flag and shows "Pair again" on the Sync screen. It **keeps** its sync key, token, cached
snapshot and receipt queue until a **new pairing succeeds**, and only then replaces the credentials. These
errors are plaintext, so a faked one must not be able to wipe anything. The next successful sync clears the flag.

| Code | Source | Phone shows | Phone action |
| --- | --- | --- | --- |
| `server_unreachable` | phone (network error/timeout, incl. health; 10 s timeout) | "Can't reach your computer. Make sure you're on home Wi-Fi and Budget Buddy is running on your computer." | Keep queue; offer **Try again**. |
| `not_home_network` | server | "Your computer only talks to phones on your home Wi-Fi. Connect to home Wi-Fi and try again." | Keep queue. |
| `bad_host` | server | "Your computer didn't recognize this connection. If your computer's network changed, pair again." | Keep everything. |
| `invalid_qr` | phone | "That's not a Budget Buddy code. On your computer, open Budget Buddy and click **Pair a phone**." | Stay on scanner. |
| `pairing_expired` | phone or server | "That pairing code has expired. Click **Pair a phone** on your computer to get a new one." | Back to scanner. |
| `too_many_attempts` | server | "Too many tries. Wait a minute, then scan the code again." | Back to scanner. |
| `not_paired` | server | "This phone isn't connected to your computer anymore. Please pair again." | *Needs attention*; keep credentials and queue. |
| `device_revoked` | server | "This phone was removed from Budget Buddy on your computer. Pair again to keep syncing." | *Needs attention*; keep credentials and queue. |
| `decrypt_failed` | server | "This phone's connection to your computer needs to be set up again. Please pair again." | *Needs attention*; keep credentials and queue. |
| `bad_response` | phone (response won't open, or `type`/`re` mismatch) | "Something on your network got in the way. Try again on your home Wi-Fi." | Discard response; keep queue. |
| `wrong_server` | phone (`server_id` ≠ stored/QR) | "This isn't the computer this phone was paired with. Pair again if you've changed computers." | Don't save anything. |
| `clock_skew` | server | "The clock on your phone or your computer is wrong. Turn on automatic date and time on both, then try again." | No automatic retry (§4.4). Keep queue. |
| `replay` | server (enc) | "Sync got interrupted. Please try again." | Retry once automatically with a new nonce. |
| `too_large` | server | "A receipt photo is too big to send. Try taking it again." | Keep queue. |
| `update_needed` | server or phone | "Budget Buddy needs an update on your phone or computer so they can talk to each other." | Stop. |
| `bad_request` / `server_error` / unknown | server or phone (no CSPRNG) | "Something went wrong. Try again in a minute." | Keep queue. |

Never show raw codes, HTTP numbers, or stack traces. Codes MAY go in a "Details" line for support.
