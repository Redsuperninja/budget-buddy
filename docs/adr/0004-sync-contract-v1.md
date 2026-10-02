# ADR-0004: Sync API contract v1

**Status:** Accepted, 2026-10-02

## Context
ADR-0002 chose home Wi-Fi sync with QR pairing and NaCl secretbox payloads, but left the wire details open.
The server work (roadmap #14, #15, #16) and the phone work (#18–#21) should be built in parallel, so both sides
need one exact spec with test vectors. A security review of the first draft pointed out that a key shown in a
QR code can be photographed, and that the Home Base's LAN surface needed explicit rules.

## Decision
Adopt [docs/api/sync-contract.md](../api/sync-contract.md) as contract version 1. Key points:
- **No secret in the QR.** The QR carries `{v, app, host, port, code, pair_pub, server_id, name, exp}`, where
  `pair_pub` is a per-session server X25519 public key. The code lasts 10 minutes, works once, and only one
  session is active. The phone sends a fresh `phone_pub` in the pair envelope. Both sides compute
  `crypto_box_beforenm` (PyNaCl `Box.shared_key()`, tweetnacl `nacl.box.before`) and use it as the secretbox
  key for the pair request and response. The response carries the token and a fresh per-device **sync key**.
  `pair_sk` is deleted when the session ends. A photo of the QR plus recorded traffic reveals nothing. An
  attacker who swaps `phone_pub` only breaks the real phone's pairing, which is visible.
  - An earlier draft put a secret key in the QR, plus an optional 6-digit code from `sha256(phone_pub)`.
    Review showed the code could be ground by an attacker holding the QR key, so it was dropped.
- **The user sees every pairing.** The dashboard shows "New phone paired: <name>" with Remove right away. The
  remaining risk, someone racing to pair with a photographed QR inside 10 minutes, is visible because the real
  phone gets `pairing_expired`. A confirmation code over `sha256(phone_pub ‖ pair_pub)` could be added later.
- **Small LAN surface:** only health, pair and sync routes face the LAN. Dashboard routes are loopback-only,
  with an Origin check and a CSRF token. There's a `Host` allowlist (DNS rebinding) and never any CORS headers.
- **All encrypted calls are `POST`** with envelope `{v, nonce, ts, box}`. The inner JSON carries `type`
  (`req`/`res`), `ts`, `method`, `path`, so captured messages can't be reflected or redirected.
- **Replay protection:** ±300 s window, plus a persisted nonce cache with a `UNIQUE` constraint on the decoded
  nonce bytes. A per-device watermark is advanced only by accepted timestamps, so a backwards clock jump fails
  closed and a forwards jump can't lock syncing out (hence no clock-offset retry on the phone). Responses echo
  the request nonce (`re`).
- **Authenticated errors:** errors after the box opens are encrypted. Plaintext errors can be faked, so they
  never make the phone delete its credentials.
- **Receipt images travel inside the envelope** (base64url), not multipart. That's one crypto code path. The
  phone downscales to ≤ 1600 px JPEG and strips EXIF, sending ≤ 5 per batch. Limits are 12 MiB per request,
  per-endpoint caps, and image checks before decoding.
- **Strict base64url** (canonical, exact lengths) and UTF-8 JSON; idempotent uploads by client UUID; token
  stored as SHA-256.

## Consequences
- Backend and mobile can build and unit-test independently against shared vectors, including the key exchange.
- The server keeps `pairing_sessions` and `seen_nonces` tables and stores sync keys encrypted at rest.
- Once a phone is paired, the Home Base stays reachable on the home network whenever it runs; the firewall
  should allow Private networks only.
- Base64 adds ~33 % to image uploads; acceptable at the downscaled size.
- Breaking changes need contract v2 and a period where the server accepts both. Changes to this contract
  require a `security-reviewer` pass; §11 of the contract is the checklist.
