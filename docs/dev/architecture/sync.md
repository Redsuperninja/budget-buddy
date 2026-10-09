# Syncing the phone

Design: [ADR-0002](../../adr/0002-wifi-qr-sync.md). The exact wire format (endpoints, envelope, snapshot and
receipt schemas, error codes, reminder rules, test vectors) is only in the
[sync contract](../../api/sync-contract.md) ([ADR-0004](../../adr/0004-sync-contract-v1.md)); this page is how
each side implements it.

## Summary

1. **Every 1–3 days**, on home Wi-Fi, the user taps **Sync now**. The phone uploads queued receipts (photo and
   details) and downloads a fresh **snapshot** (budget breakdown, recent transactions, account balances, tax
   summary).
2. Every sync payload is **encrypted end-to-end with the sync key** (NaCl secretbox), so even plain HTTP on the
   home network can't be snooped. Requests also need the device token.
3. Only health, pairing and sync routes answer phones on the home network; everything else answers this computer
   only, or a computer joined with a one-time code ([remote-computers.md](remote-computers.md)).
   Phones can be removed from the dashboard ([pairing.md](pairing.md)).

## Server side (roadmap #15)

Code: `routers/sync.py`, `services/sync.py`, `sync_context.py`, `sync_receipts.py`, `snapshot.py`,
`snapshot_tax.py`, and `services/envelope.py` (opening and sealing, shared with `/api/pair`).

- The phone's token is checked **before** the body is read. The body is read with a hard limit that stops at the
  limit (`app/bodylimit.py`): 16 KiB, or 12 MiB for receipts.
- Every request follows the contract's §4.4 order: `Host`/network checks, token, body, `ts` window and
  per-device watermark, open the box with the device's sync key, check the inner `type`/`ts`/`method`/`path`,
  then insert `(device_id, nonce bytes, ts)` into `seen_nonces` (`UNIQUE(device_id, nonce)`; a failed insert
  is an encrypted 409 `replay`).
- The watermark (`devices.nonce_watermark`) only moves with accepted requests (`ts − 600`) and old nonces are
  pruned below it. Revoking a phone deletes its nonces.
- From the replay check on, every answer is encrypted, including errors; unexpected failures return a fixed
  `server_error` message. Before that, errors are plain `{"error": {"code", "message"}}` (for example
  `not_paired`, `device_revoked`, `clock_skew`, `decrypt_failed`, `too_large`). The home-network
  middleware's 403 uses the same shape (`not_home_network`).
- A phone removed while its body was arriving is re-checked in the nonce transaction and gets a plain 401.

### Routes (home network and this computer; `Authorization: Bearer <device token>`)

- `POST /api/sync/snapshot` (≤ 16 KiB): built from the existing services (monthly summary, account balances,
  paychecks, donations, stock gains, deductions) and containing only the fields §5 lists: this month's budget
  by group and category plus unassigned money, the last 60 days of transactions (at most 500), every account's
  balance up to today, income received and expected, and tax totals. Income is the summary's income (paychecks
  only raise `expected`). No account numbers, notes, receipt photos or employer names.
- `POST /api/sync/receipts` (≤ 12 MiB): 1 to 5 receipts, each a JPEG (≤ 3 MiB, ≤ 4096 px a side, ≤ 16 MP, read
  from the header before anything is decoded). Saved through the receipts service and `EncryptedFileStore`. One
  result per item: `accepted`, `duplicate` (this phone already sent that `client_id`; nothing new is stored) or
  `rejected` with a reason; another phone's `client_id` is `rejected`. Idempotency uses `receipts.client_id`
  (unique) with `receipts.device_id`.
- `POST /api/sync/ack` (≤ 16 KiB): the phone finished a sync; sets `devices.last_sync_at`.

Tables and columns for sync came in migration 0008 ([database.md](database.md)).

## Phone side

Contract sections followed: 3.5, 3.8, 3.9, 4, 7.2 and 8. Code: `mobile/src/sync/syncClient.ts` (`syncNow()`),
`runSync.ts` (one sync at a time, every outcome in plain English), `transport.ts`, `snapshot.ts` and
`snapshotChecks.ts` / `snapshotSections.ts` (`parseSnapshot()`), `store.tsx` (`useSnapshot()`), and
`mobile/src/components/SyncPanel.tsx` (the **Sync now** button on Home and Settings).

1. `GET /api/health` first, so "computer not reachable" is told apart from other problems. It must report
   `contract: 1`, otherwise the phone asks for an update.
2. Receipt upload: a hook only (`SyncDeps.uploadReceipts`) until roadmap #20.
3. `POST /api/sync/snapshot` with a fresh random nonce. The answer must open, be `type: "res"`, and have `re`
   equal to our nonce, or it is thrown away (`bad_response`). The snapshot must pass `parseSnapshot()` and carry
   this computer's `server_id`; only then is it saved. That moment counts as a successful sync.
4. `POST /api/sync/ack`, best effort; failures are not shown.

Safety rules:

- Plaintext errors are unauthenticated, so they only show a message (and, for `not_paired`, `device_revoked`
  and `decrypt_failed`, a **Pair again** button). They never delete the token, sync key or saved snapshot.
- An encrypted `replay` answer is retried once with a new nonce. `clock_skew` is never retried with the
  server's clock.
- Every request times out after 10 s (`AbortController`); redirects are never followed; the saved address must
  still be a private or loopback IP with a valid port (checked in `transport.ts`, so health and pairing too).
- Answer size is capped (16 KiB, snapshot 2 MiB). A `Content-Length` over the cap is refused up front; with a
  streaming body the phone counts bytes and aborts at the cap. **Limitation:** React Native's `fetch` may not
  stream, in which case the whole answer is read and then measured (the 10 s timeout still applies).
- The saved snapshot is in AsyncStorage (no keys in it), protected by the phone's lock. Encrypting it at rest is
  issue #19: secure-store has a small size limit, so it needs a key in secure-store plus an encrypted file.
