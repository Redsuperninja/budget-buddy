# Security and privacy

Decisions: [ADR-0003](../../adr/0003-encryption-at-rest.md) (at rest), [ADR-0002](../../adr/0002-wifi-qr-sync.md)
and [ADR-0004](../../adr/0004-sync-contract-v1.md) (on the network). Checklist for reviewers: sync contract §11.

## At rest

- The master key lives in the OS password vault (Windows Credential Manager, macOS Keychain, Linux Secret
  Service, via `keyring`), never in files. The data folder holds only a `key-fingerprint` to check the key
  belongs to it. Only derived keys (fields, files, backup) are kept in memory.
- Sensitive columns (account numbers, notes, device sync keys, pairing secret keys, the Finnhub key) use the encrypted column
  types in `app/crypto/fields.py`. Never add plaintext copies.
- Receipt photos are encrypted (AES-256-GCM, `EncryptedFileStore`) before they're written, under random file
  names. The plain photo is never written to disk.
- **Recovery phrase:** `python -m app recovery-phrase show` prints it after the user types `SHOW` (terminal
  only, never a file, after checking it matches the data folder); `restore` puts the key back.
- The memory key store is for automated tests only and needs a second switch ([../testing.md](../testing.md)).
- Backup copies `budget.db.bak-0001`/`-0002` predate encryption and are plaintext; the Home Base tells the user
  so they can delete them.
- Planned: an encrypted single-file backup export the user can copy to a USB drive.

## The desktop app and a Home Base already running

The window shows a Home Base it didn't start only after a challenge-response with a per-run key kept in the
private data folder (`home-base-running.json`: port, process ID, 32-byte key as hex; [desktop.md](desktop.md)).
The proof is `hex(HMAC-SHA256(key, nonce as ASCII))` for a fresh hex nonce, compared in constant time; both
parts compute it this way (`server/app/instance_proof.py`, `desktop/budget_buddy_desktop/genuine.py`). The file is
written only after the port is bound (a second copy that can't bind leaves it alone), removed on shutdown, and
ignored when its process isn't running. The key is never logged or sent; the proof route answers this computer
only, and the desktop's local requests skip any proxy.

## The one outside connection: live prices

Off unless turned on ([ADR-0010](../../adr/0010-live-stock-prices.md)). The Home Base (never the browser) sends
only held symbols to Finnhub over HTTPS, on demand; the key is an encrypted column (`price_feed.api_key`), never
returned by the API, and sent only in a request header; redirects are never followed and certificates always
checked. A system proxy, if set, is used: HTTPS passes through it as a tunnel, so only a TLS-inspecting proxy could
see the key. Turning it on or changing the key is this computer only. Tests replace the opener and fail if anything
tries to reach the network.

## Never cached

Every `/api/*` reply carries `Cache-Control: no-store` (`app/network.py`), so neither a browser nor the desktop
app's window keeps financial data in its disk cache.

## What stays plain text in `budget.db`

These stay readable so Budget Buddy can search, sort and add them up:

- every amount and date, and each transaction's description
- auto-sort rule text (`category_rules.pattern`), which is copied from transaction descriptions
- shop names on receipts (`receipts.merchant`)
- employer names and gross/net pay on paychecks (`paychecks.employer`)
- account names and banks (`accounts.name`, `accounts.institution`)
- charity names on donations (`donations.organization`)
- stock symbols and lots

Encrypting more of them, or the whole database, is
[issue #28](https://github.com/Redsuperninja/budget-buddy/issues/28). Users are told to keep the data folder out
of cloud-synced folders and to protect their Windows account with a password.

## On the network

| Routes | Who may call |
| --- | --- |
| `GET /api/health`, `POST /api/pair`, `POST /api/sync/*` | This computer and the home network (private addresses only; others get 403 `not_home_network`) |
| Dashboard pages, `/static/*`, `POST /api/remote/join` | This computer, and the home network (the page has no CSRF token until a computer joins) |
| `/api/local/...` | This computer, and computers joined with a one-time code, except pairing, joining and the scripts' token ([remote-computers.md](remote-computers.md); 403 `not_this_computer`) |

Every route also checks the `Host` header, and dashboard writes check `Origin` and the CSRF token
([server.md](server.md), [dashboard.md](dashboard.md)). The home-network listener is opened only while it's
needed ([pairing.md](pairing.md)). Sync payloads are encrypted and replay-checked ([sync.md](sync.md)).

A joined computer can do anything the dashboard can, including bulk changes: undoing a whole import
(`DELETE /api/local/imports/{id}`) is one request, behind a confirm box.

Joined computers talk plain HTTP on the home network (no app-level encryption, unlike phones), so the guide
limits it to trusted home networks ([ADR-0009](../../adr/0009-other-computers.md)).

## Logs

Never log secrets, tokens, keys, file contents, pairing payloads, or amounts together with descriptions.
