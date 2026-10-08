# Pairing a phone

Design: [ADR-0002](../../adr/0002-wifi-qr-sync.md). Wire format: [sync contract §2 and §3.6](../../api/sync-contract.md).
User guide: [docs/guide/](../../guide/).

## Flow (once per phone)

The dashboard shows a QR code with the computer's home-network address, a one-time pairing code, and a
short-lived **public** key. There's no secret in the QR. The phone sends its own fresh public key, both sides
derive a shared key, and the Home Base answers, encrypted with it, with a device token and a new **sync key**.
The phone keeps both in secure storage. The dashboard immediately shows "New phone paired" with a Remove button.

## Server side (roadmap #14)

`services/pairing_sessions.py` (sessions, server ID, listener wishes) and `services/pairing.py` (the
`/api/pair` handshake), using `services/envelope.py` to open and seal.

- `POST /api/local/pairing` (this computer only) makes a session: a 16-byte one-time code (only its SHA-256 is
  stored), a fresh X25519 keypair (`pair_sk` stored encrypted, erased when the session ends), valid for 10
  minutes, once. Starting a new one cancels the old one. It returns:
  - `payload` (the QR contents as JSON) and `payload_text` (the same as one line, for "Show code as text");
  - `qr_svg` (the QR drawn by `segno`) and `expires_at`;
  - `phone_can_connect` with a plain-English `message` if a phone can't reach this computer yet.
  Never log or save the result.
- `POST /api/pair` (phone, home network): encrypted and authenticated, replay-checked (nonces kept per session
  in `pairing_nonces`), limited to 10 tries a minute per address, and 5 wrong codes end the session. Only a hash
  of the device token is kept; the sync key is stored encrypted. Errors use the contract's codes (§3.4).

## Devices

- `GET /api/local/devices` lists phones: name, platform, app version, when paired, last sync, removed or not.
  Never tokens, codes or keys. The dashboard polls it about every 3 seconds while a QR is showing.
- `POST /api/local/devices/{id}/revoke` marks a phone removed, deletes its sync key and its `seen_nonces`, so
  its token stops working at once. The row stays as history.

## Home-network listener (`app/listeners.py`, `app/lan.py`)

- The main server listens on `127.0.0.1` only. While a pairing session is live, or while at least one phone is
  paired, `python -m app` also opens a second listener on this computer's own home-network address
  (`BUDGET_BUDDY_LAN_IP`, or detected), **never `0.0.0.0`**, and closes it when neither is true.
- It is re-checked when pairing starts, a phone is removed, and the device list is read. There is no timer: a
  listener for an expired, unused QR is closed at the next check.
- An explicit `BUDGET_BUDDY_HOST` wins: loopback means phones can never connect (pairing says so); any other
  address is used as the main listener (not recommended).
- The `Host` allowlist includes `{lan address}:{port}`. Requests from outside private networks get 403.
- Windows Firewall asks once whether to allow Python; the user should allow **Private networks** only.

## Phone side (roadmap #18)

`mobile/src/app/pair.tsx` and `mobile/src/sync/`: `pairingQr.ts` (checks the QR), `pairClient.ts` (the
`/api/pair` call), `pairErrors.ts` (plain-English messages), `credentials.ts`, `base64url.ts`, and
`transport.ts` (shared with sync: secure random numbers, one HTTP request with a 10 s timeout, the envelope).

- The screen reads the QR with the camera, or the user types or pastes its text. Scanning is turned off on the
  web build, so the scanner never loads code from the internet.
- It checks the QR (known version, the address is a private home-network IP, code not expired), sends one
  encrypted `POST /api/pair`, and checks the answer is for that request and from the same computer.
- **Secure storage:** the device token, sync key and computer address go into `expo-secure-store` only after the
  whole pairing succeeded, replacing any old ones. The temporary pairing keys are never saved or logged.
- **Different computer:** if the phone is already connected and the code is from another computer, the screen
  asks first. Cancel keeps the old connection.
- Right after pairing succeeds the phone runs its first sync ([sync.md](sync.md)).
- The packages it relies on are listed in [mobile/README.md](../../../mobile/README.md).
