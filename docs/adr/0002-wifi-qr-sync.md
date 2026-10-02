# ADR-0002: Home Wi-Fi sync with QR pairing and end-to-end encrypted payloads

**Status:** Accepted, 2026-10-02

## Context
The user is non-technical. Sync doesn't need to be live; every 1–3 days is fine. Data must not leave the
home network. HTTPS with a self-signed certificate on a LAN is confusing for users and certificate pinning
isn't available in Expo Go.

## Decision
- **Pairing:** the Home Base dashboard shows a QR code with `{host, port, pairing_code, key}` where `key` is a
  random 32-byte secret and `pairing_code` expires after 10 minutes and works once. The phone stores `key` and
  the issued device token in secure storage.
- **Transport:** HTTP on the LAN, with every sync payload encrypted and authenticated using NaCl `secretbox`
  (XSalsa20-Poly1305): PyNaCl on the server, tweetnacl on the phone. Each request includes a timestamp and
  nonce to prevent replays.
- **Access control:** device token (stored hashed on server) on every request; server rejects non-private source IPs;
  devices can be revoked.
- **Reminders:** the phone schedules a local notification when the last successful sync is older than N days
  (default 2, user-selectable 1–3).

## Consequences
- Someone on the same Wi-Fi sees only encrypted blobs and can't forge requests.
- Losing the phone: revoke the device on the Home Base; the phone's cached snapshot is protected by the OS lock + secure store key.
- Works away from home: no (by design for now). A future ADR may add an optional relay.
