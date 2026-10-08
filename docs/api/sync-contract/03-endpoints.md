Part of the [Sync API contract, v1](../sync-contract.md). Conventions and key names are in §1 there.

## 3. Endpoints

### 3.1 Which routes face the network

| Route group | Who may call | Notes |
| --- | --- | --- |
| `GET /api/health`, `POST /api/pair`, `POST /api/sync/*` | Loopback **and** LAN (private-network middleware) | The only LAN-facing routes. |
| Everything else: dashboard pages, start pairing / get QR, list / approve / revoke devices, imports, … | **Loopback clients only** (socket peer address is `127.0.0.0/8` or `::1`; never trust `X-Forwarded-For`) | Others get 403 `not_this_computer`. |

All routes, both groups:
- **Host header allowlist.** `Host` MUST be exactly one of `127.0.0.1:{port}`, `localhost:{port}`,
  `[::1]:{port}`, or `{configured LAN IP}:{port}` (IPv6 LAN IP in brackets). Otherwise 403 `bad_host`. This
  stops DNS-rebinding pages in the user's browser from talking to the Home Base.
- **No CORS.** The server MUST NOT send any `Access-Control-Allow-*` header, on any route, ever.

State-changing dashboard routes (any non-GET) additionally require:
- `Origin` header present and equal to `http://127.0.0.1:{port}`, `http://localhost:{port}` or
  `http://[::1]:{port}`, else 403 `bad_origin`.
- A CSRF token: random per dashboard session, embedded in the page, sent back in `X-CSRF-Token`, compared in
  constant time, else 403 `bad_origin`.

**Staying reachable.** Once at least one phone is paired, the Home Base listens on the LAN (`0.0.0.0` or the
LAN interface) whenever it runs. There is no on/off switch for the listener; the protections above are what
keep it safe. (Before the first pairing, the default `127.0.0.1` from `config.py` applies; starting a pairing
session switches to the LAN listener.) When Windows Firewall asks, the user guide (#23) and the dashboard tell
the user to allow **Private networks** only, never Public.

### 3.2 LAN endpoints

| Method & path | Auth | Purpose | Body limit |
| --- | --- | --- | --- |
| `GET /api/health` | none | "Is Budget Buddy running?" (exists today) | n/a |
| `POST /api/pair` | pairing key agreement (no token) | Exchange the code for a token + sync key | 16 KiB |
| `POST /api/sync/receipts` | token + sync key | Upload a batch of queued receipts | 12 MiB |
| `POST /api/sync/snapshot` | token + sync key | Download a fresh snapshot | 16 KiB |
| `POST /api/sync/ack` | token + sync key | Tell the server the sync finished | 16 KiB |

**Why the snapshot is `POST`, not `GET`:** every encrypted request carries a fresh nonce and timestamp
inside an encrypted body (§4). A `GET` has no body, and putting the envelope in a header or URL would add a
second code path and leak into logs.

Body limits are enforced **while streaming** (stop reading at the limit; don't trust `Content-Length` alone),
and on `/api/sync/*` the token is checked **before** the body is read. Over the limit → 413 `too_large`.

### 3.3 Request headers

| Header | When | Value |
| --- | --- | --- |
| `Content-Type` | all `POST` | `application/json` |
| `Authorization` | all `/api/sync/*` | `Bearer <device token>` |
| `User-Agent` | optional | e.g. `BudgetBuddy-Mobile/1.0.0` (diagnostics only) |

`/api/pair` has no `Authorization` header; the server uses the single active session's `pair_sk` (§2.4).

### 3.4 Responses and errors

**Encrypted responses.** Once the server has opened a request's box, **every** answer, success or error, is
an encrypted response envelope (§4.3). The HTTP status equals the inner `status`. Success is 200 with `data`;
errors carry `error` instead:

```json
{ "type": "res", "ts": 1790000001, "re": "<request nonce>", "status": 409,
  "error": { "code": "replay", "message": "Sync got interrupted. Please try again." } }
```

**Plaintext errors.** Errors that happen *before* the box opens (or if it can't be opened) are plaintext JSON,
since there's no key to use yet. They contain no user data:

```json
{ "error": { "code": "clock_skew", "message": "The clock on your phone or your computer is wrong. Turn on automatic date and time on both, then try again.", "server_time": 1790000000 } }
```

- `code` is stable and machine-readable; the phone switches on it (§7). `message` is plain English and is a
  fallback; the phone prefers its own text for codes it knows.
- Extra fields per code: `server_time` (`clock_skew`), `supported` (`update_needed`).
- **Plaintext errors are unauthenticated** (anyone on the Wi-Fi can fake one). The phone MUST NOT delete its
  sync key, token or queue because of one (§7.2).
- `server_error` messages are fixed text. Never include exception text, stack traces, paths or SQL.
- The existing middleware's 403 body (`{"detail": ...}`) MUST be migrated to this format with code
  `not_home_network` in #15. Until then, the phone treats any plaintext 403 without an `error` body as
  `not_home_network`.

| HTTP | `code` | Form | When |
| --- | --- | --- | --- |
| 400 | `bad_request` | plain | Not JSON, wrong content type, envelope fields missing, bad base64url, wrong decoded length (§4.6). |
| 400 | `bad_request` | **enc** | Inner JSON fails validation (missing/wrong fields in `data`). |
| 400 | `clock_skew` | plain | `ts` more than 300 s from server time, or below the device's replay watermark (§4.4). |
| 401 | `not_paired` | plain | Missing/unknown token on `/api/sync/*`. |
| 401 | `device_revoked` | plain | Token belongs to a revoked device. |
| 401 | `decrypt_failed` | plain | Box doesn't open, or inner `type`/`ts`/`method`/`path` don't match. |
| 403 | `not_home_network` | plain | Source address isn't private. |
| 403 | `bad_host` | plain | `Host` header not on the allowlist. |
| 403 | `not_this_computer` | plain | Dashboard route called from a non-loopback address. |
| 403 | `bad_origin` | plain | Dashboard write without matching `Origin` or CSRF token. |
| 409 | `replay` | **enc** | Nonce already used by this device (§4.4). |
| 410 | `pairing_expired` | plain / **enc** | No active session, expired, used, cancelled (plain); wrong code (enc). |
| 413 | `too_large` | plain | Body over the endpoint's limit. |
| 426 | `update_needed` | plain / **enc** | Envelope `v` unsupported (plain); inner `contract` unsupported (enc). Includes `"supported": [1]`. |
| 429 | `too_many_attempts` | plain | `/api/pair` rate limit hit. |
| 500 | `server_error` | plain / **enc** | Anything unexpected. Fixed message only. |

### 3.5 `GET /api/health`

No auth. Response (200, plaintext): `{ "status": "ok", "version": "0.1.0", "contract": 1 }`.
`contract` is added by #14/#15. The phone calls this first on every sync to tell "computer not reachable" apart
from other failures, and to catch an old Home Base.

### 3.6 `POST /api/pair`

The pair envelope is the normal request envelope plus one plaintext field, `phone_pub`. Its secretbox key is
`shared` (§2.4):

```json
{ "v": 1, "nonce": "<24 bytes>", "ts": 1790000000, "phone_pub": "ST6C_HRGSlkmiBdiPSBTxeuOLMSpiLT-4XnsawENUx0", "box": "<bytes>" }
```

Inner request `data`:

```json
{
  "code": "pQ3mX9vT2aLk8RzN1bWc4g",
  "device_name": "Ana's iPhone",
  "platform": "ios",
  "app_version": "1.0.0"
}
```

- `phone_pub`: 32 bytes, fresh for every pairing attempt. `device_name`: 1–50 chars, shown on the dashboard.
  Phone pre-fills from the device model; user can edit. `platform`: `"ios"` or `"android"`.

Server steps: per-IP rate limit → active session exists → decode `phone_pub` (32 bytes, else 400) →
`shared = Box(pair_sk, PublicKey(phone_pub)).shared_key()` → open the box (else plaintext 401
`decrypt_failed`, not counted) → inner checks (§4.4) → constant-time compare `sha256(code)` (wrong → enc 410,
counts toward 5) → atomic claim (§2.3) → create the device row → generate `token` and `sync_key` → reply →
delete `pair_sk` → notify the dashboard (§2.5).

Inner response `data` (response envelope encrypted with `shared`):

```json
{
  "device_id": 3,
  "token": "YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8",
  "sync_key": "4OHi4-Tl5ufo6err7O3u7_Dx8vP09fb3-Pn6-_z9_v8",
  "server_id": "Zk3pR7tQ1xYb9mWc2nLs5Q",
  "server_name": "Home Base"
}
```

- `token`: 32 random bytes. Server stores `token_hash = sha256(token as ASCII bytes)`, lowercase hex, and
  looks devices up by it. `sync_key`: 32 random bytes, stored on the server encrypted at rest (ADR-0003).
- Phone MUST open the response with `shared` and check `type`/`re` (§4.3), check `server_id` equals the QR's
  (`wrong_server`), then save `{host, port, sync_key, token, server_id, server_name, device_id}` in
  `expo-secure-store`, replacing any previous credentials **only now**, after this pairing fully succeeded.
  Then discard `phone_sk` and `shared`, and run a first sync (§8).

### 3.7 `POST /api/sync/receipts`

Inner request `data`: `{ "receipts": [ReceiptUpload, ...] }`, 1–5 items. See §6.
Inner response `data`: `{ "results": [ReceiptResult, ...] }`, one per item, same order. Per-item problems
never fail the whole request.

### 3.8 `POST /api/sync/snapshot`

Inner request `data`: `{}` (reserved for future options). Inner response `data`: a `Snapshot` (§5).

### 3.9 `POST /api/sync/ack`

Inner request `data`:
`{ "snapshot_generated_at": "2026-10-02T18:30:00Z", "receipts_uploaded": 2, "app_version": "1.0.0" }`.
Server sets `devices.last_sync_at = now` (dashboard: "Last synced 2 hours ago").
Inner response `data`: `{ "last_sync_at": "2026-10-02T18:30:01Z" }`. Best-effort (§8).

### 3.10 Revoking a device

Revoking (dashboard **Remove**) marks the device revoked, **deletes its
`sync_key`** and **deletes its `seen_nonces` rows**. The row itself stays so the dashboard can show history.
Later requests with that token get plaintext 401 `device_revoked`.
