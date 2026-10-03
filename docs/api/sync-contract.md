# Sync API contract, v1

**Status:** Accepted (see [ADR-0004](../adr/0004-sync-contract-v1.md)) · **Contract version:** `1`

This is the single spec the Home Base (`server/`, roadmap #14, #15, #16) and the phone app (`mobile/`,
roadmap #18–#21) build against. If the two sides follow this document and pass the test vectors in §4.7, they
interoperate. Background: [ADR-0002](../adr/0002-wifi-qr-sync.md) (Wi-Fi + QR + secretbox) and
[ADR-0003](../adr/0003-encryption-at-rest.md) (encryption at rest). The short list of things each PR must
get right is in **§11, Security requirements**.

The words MUST, MUST NOT, SHOULD and MAY are used in their RFC 2119 sense.

---

## 1. Conventions

| Thing | Rule |
| --- | --- |
| Money | Integer cents (`*_cents`), JSON numbers with no fraction. Never floats. Currency is the snapshot's `currency`. |
| Dates | ISO `YYYY-MM-DD`, in the Home Base's local calendar. |
| Date-times | RFC 3339 in UTC with a `Z` suffix, e.g. `2026-10-02T18:30:00Z`. Phone-supplied `captured_at` MAY carry an offset instead. |
| Months | `YYYY-MM`. |
| Unix time | Integer seconds since the epoch (`ts` fields). |
| Binary → text | **Strict base64url without padding** (RFC 4648 §5), everywhere. Rules and helpers in §4.6. |
| JSON | UTF-8, no BOM. Unknown fields MUST be ignored by the receiver (forward compatibility). |
| IDs | Server row IDs are integers. Client-generated IDs are lowercase UUID v4 strings. |
| Names | `snake_case` field names on the wire, on both sides. |

### 1.1 Keys and secrets at a glance

| Name | Size | Made by | Lives | Purpose |
| --- | --- | --- | --- | --- |
| pairing keypair (`pair_pub`, `pair_sk`) | X25519 | server, per QR | `pair_pub` in the QR (public); `pair_sk` on the server only, deleted when the session ends | Pairing key agreement (§2.4). |
| phone keypair (`phone_pub`, `phone_sk`) | X25519 | phone, per pairing | phone memory during pairing only | Pairing key agreement (§2.4). |
| `shared` | 32 B | both sides, `crypto_box_beforenm` | memory during pairing only | Secretbox key for the `/api/pair` request and response. |
| `code` | 16 B | server, per QR | QR; server stores `sha256(code)` | One-time pairing code. |
| `sync_key` | 32 B | server, per device | server (encrypted at rest), phone secure store | Encrypts every sync request and response. **Never appears in the QR.** |
| device `token` | 32 B | server, per device | phone secure store; server stores `sha256` | Selects the device. |
| `server_id` | 16 B | server, once | server, QR, phone | Checks the phone is talking to the same Home Base. |

---

## 2. Pairing

### 2.1 QR payload

The Home Base dashboard shows a QR code when the user clicks **Pair a phone**. It contains exactly this
JSON object (compact or pretty; order doesn't matter):

```json
{
  "v": 1,
  "app": "budget-buddy",
  "host": "192.168.1.20",
  "port": 8765,
  "code": "pQ3mX9vT2aLk8RzN1bWc4g",
  "pair_pub": "YFpyXSpK3-6xop4X7dYhwbdZPujNvESsbEq24vgF0jw",
  "server_id": "Zk3pR7tQ1xYb9mWc2nLs5Q",
  "name": "Home Base",
  "exp": 1790000600
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `v` | int | Contract version. Phone MUST refuse versions it doesn't know (`update_needed`). |
| `app` | string | Always `"budget-buddy"`. Lets the phone reject unrelated QR codes (`invalid_qr`). |
| `host` | string | The computer's LAN IP address (IPv4 dotted, or IPv6 without brackets). Not a hostname. |
| `port` | int | HTTP port (default `8765`). |
| `code` | string | One-time pairing code: 16 random bytes (22 chars). |
| `pair_pub` | string | The session's X25519 **public** key (32 bytes, 43 chars). Not a secret. Used only for `/api/pair`. |
| `server_id` | string | Random 16 bytes (22 chars), created on the Home Base's first run. |
| `name` | string | Friendly name to show on the phone. ≤ 50 chars. |
| `exp` | int | Unix time when the code expires (issue time + 600 s). |

Phone checks before calling `/api/pair`, failing with the error shown:
- `app`, `v`, all fields present, `pair_pub`/`code`/`server_id` decode to exactly 32/16/16 bytes (`invalid_qr`).
- `host` is an IP literal in a private, loopback or link-local range, the same list as the server's
  `ALLOWED_NETWORKS` in `server/app/network.py`. Anything else, including hostnames and public IPs, is `invalid_qr`.
- `exp` hasn't passed (`pairing_expired`).

The phone builds the base URL as `http://{host}:{port}` (IPv6: `http://[{host}]:{port}`).

### 2.2 QR encoding and handling

- QR byte mode, the JSON as UTF-8 text, error-correction level **M**. No URL scheme or prefix. ~250 bytes.
- The dashboard fetches the payload (or a rendered QR image) from a **loopback-only** route (§3.1) with
  `Cache-Control: no-store`. The payload MUST NOT appear in any URL (path or query string) and MUST NOT be
  written to any log, on either side.

### 2.3 Session lifetime (server)

- A code is valid for **10 minutes** and works **once**. Starting a new QR cancels any unused one, so
  **at most one pairing session is active** at a time.
- Server stores `sha256(code)`, `pair_pub`, `pair_sk` (in memory, or encrypted at rest), `exp`, `used_at`, and
  a wrong-code counter. `pair_sk` is **deleted as soon as the session ends** (used, expired, cancelled).
- **Wrong code** (box opened with the shared key, but `code` doesn't match): counts toward a limit of **5**,
  after which the session is cancelled. **Failed decrypts do not count** (anyone on the Wi-Fi could send
  garbage and lock the user out). Instead `/api/pair` has a **per-IP rate limit** of 10 requests per minute
  (429 `too_many_attempts`).
- Claiming the session is a single **atomic conditional update**, e.g.
  `UPDATE pairing_sessions SET used_at = :now WHERE id = :id AND used_at IS NULL AND exp > :now`, and the
  pairing proceeds only if exactly one row changed. Two phones racing for one QR: one wins, the other gets
  `pairing_expired`.
- Anyone who can see the screen can attempt to pair. §2.5 makes sure the user notices and can undo it.

### 2.4 Key agreement: no secret in the QR

The QR holds only public values, so a photo of it doesn't let anyone read the pairing exchange. During
`/api/pair`:

1. Phone generates a fresh X25519 keypair with `nacl.box.keyPair()` (tweetnacl). It sends `phone_pub`
   (32 bytes) as a **plaintext field of the outer pair envelope** (§3.6).
2. Both sides compute the same 32-byte key with NaCl `crypto_box_beforenm`:
   - phone (tweetnacl): `shared = nacl.box.before(pair_pub, phone_sk)`
   - server (PyNaCl): `shared = Box(pair_sk, PublicKey(phone_pub)).shared_key()`
3. `shared` is the secretbox key for the pair **request** and **response** envelopes, which are otherwise the
   normal envelopes of §4. (`nacl.box.after` / `Box.encrypt` with that key give the same bytes as secretbox.)
4. The response carries the device `token` and a freshly generated random 32-byte `sync_key`. The phone stores
   them and discards `phone_sk` and `shared`. The server deletes `pair_sk` when the session ends.

What this protects against:
- **Someone with a photo of the QR who also records the Wi-Fi traffic** can't compute `shared` (they'd need
  `pair_sk` or `phone_sk`), so they never see the token or the `sync_key`.
- **Someone who swaps `phone_pub` in transit** gets a response only they can open. The real phone then can't
  open its response (`bad_response`), and the session is used up. The user sees a failed pairing on the phone
  and a device they don't recognize on the dashboard (§2.5).
- **Remaining risk, accepted:** someone with a photo of the QR pairs their own device first, within the 10
  minutes. That's visible: the real phone gets `pairing_expired`, and the dashboard shows
  "New phone paired: &lt;name&gt;" with **Remove**.

### 2.5 Telling the user

- As soon as a pairing succeeds, the dashboard **MUST** show **"New phone paired: &lt;device_name&gt;"** with a
  **Remove** (revoke) button, without the user having to refresh or open a settings page. If the phone
  shows an error after scanning, the dashboard text tells the user: "Didn't pair a phone just now? Click Remove."
- There is no confirmation code in v1, to keep pairing a one-step action. A future contract version could add
  a short code derived from `sha256(phone_pub ‖ pair_pub)`, shown on both screens, if wanted.

---

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

---

## 4. Encryption envelope

### 4.1 Algorithm, keys, randomness

- NaCl **secretbox** = XSalsa20-Poly1305. Server: PyNaCl `nacl.secret.SecretBox`. Phone: `tweetnacl`
  `nacl.secretbox`.
- Key: `shared` (§2.4) for `/api/pair`, the device's **sync key** for `/api/sync/*`.
- Nonce: **24 bytes from a CSPRNG, fresh for every message** (requests and responses). Never a counter.
- **Phone randomness:** use `expo-crypto` `getRandomBytes` and install it with `nacl.setPRNG`. If no
  CSPRNG is available, the phone MUST fail closed (refuse to pair or sync, show `server_error`-style text) and
  MUST NEVER fall back to `Math.random`.
- `box` = the secretbox output: 16-byte Poly1305 tag followed by the ciphertext (length = plaintext + 16).
  This is exactly tweetnacl's `nacl.secretbox(...)` and PyNaCl's `SecretBox(key).encrypt(pt, nonce).ciphertext`.
  **Do not** send PyNaCl's default `encrypt()` result, which prepends the nonce.

### 4.2 Request envelope

The HTTP body of every encrypted request:

```json
{ "v": 1, "nonce": "<24 bytes>", "ts": 1790000000, "box": "<bytes>" }
```

`box` opens to the UTF-8 bytes of this JSON object (the "inner request"):

```json
{ "type": "req", "ts": 1790000000, "method": "POST", "path": "/api/sync/snapshot", "contract": 1, "data": { } }
```

| Inner field | Rule |
| --- | --- |
| `type` | Required, MUST be `"req"`. Requests and responses share a key, so this stops a captured response being fed back as a request (and vice versa: responses MUST have `"res"`). |
| `ts` | MUST equal the outer `ts`. The outer copy allows a cheap early reject; the inner copy is authenticated. |
| `method`, `path` | MUST match the actual HTTP method and path (no query string). Stops a captured box being replayed against another endpoint. |
| `contract` | `1`. |
| `data` | The endpoint's request object (§3). |

The inner JSON is never re-serialized for verification (the box authenticates the bytes), so whitespace and
key order don't matter.

### 4.3 Response envelope

Same outer shape `{v, nonce, ts, box}`, new random nonce, server's current `ts`. Inner response:

```json
{ "type": "res", "ts": 1790000001, "re": "<the request's nonce>", "status": 200, "data": { } }
```

(`error` instead of `data` when `status` ≠ 200, §3.4.) The phone MUST check `type == "res"` and `re` equals the
nonce it sent. This binds the answer to the request, so nobody on the Wi-Fi can replay an old snapshot at the
phone. If the box doesn't open or a check fails, the phone reports `bad_response` and discards it.

### 4.4 Server verification order (and replay protection)

1. Private-network check, `Host` allowlist (§3.1).
2. `/api/sync/*`: token present (else 401 `not_paired`), strictly decodes to 32 bytes (else 400
   `bad_request`), found by `sha256(token)` (else 401 `not_paired` / `device_revoked`), all **before reading
   the body**. `/api/pair`: per-IP rate limit, active session exists (else 410).
3. Read the body up to the endpoint limit (§3.2). Parse the outer JSON; `v` must be `1` (else 426).
   `nonce` decodes to exactly 24 bytes, `box` to ≥ 16 bytes, `ts` is an integer, and for `/api/pair`
   `phone_pub` decodes to exactly 32 bytes (else 400).
4. `|server_now − ts| ≤ 300` s, and for `/api/sync/*` `ts ≥ W` (the device's watermark, below), else 400
   `clock_skew`.
5. Open the box with the device's `sync_key`, or for `/api/pair` with `shared` (§2.4) (else 401 `decrypt_failed`).
6. Inner `type == "req"`, `ts == outer ts`, `method`/`path` match (else 401 `decrypt_failed`); `contract`
   supported (else enc 426). **From here on, all errors are encrypted.**
7. **Replay cache:** insert `(device_id, nonce_bytes, ts)` into `seen_nonces`, which has a **UNIQUE
   constraint on `(device_id, nonce)`**, keyed on the **decoded 24 nonce bytes** (not the base64 text). A
   failed insert means **replay** (enc 409). Insert-then-check, never check-then-insert. The table is in
   SQLite so it survives restarts. For `/api/pair`, use the pairing session ID in place of `device_id`.
8. Validate `data`, do the work, reply.

**Pruning that survives clock jumps.** Each device has a persisted **watermark** `W` (initially 0, a column on
`devices`). It moves only with **authenticated, accepted** timestamps, never with the server clock alone:
after a request passes step 7, set `W = max(W, ts − 600)` (600 s = twice the window), then delete that
device's `seen_nonces` rows with `ts < W`. Step 4 rejects `ts < W`, so a request in the pruned range can never
slip past the cache.
- Clock jumps **backwards**: requests older than `W` are refused (fail closed, shown as `clock_skew`) until the
  clock is right again.
- Clock jumps **forwards**: `W` doesn't move, because the window check rejects those requests before they're
  accepted. Syncing works again as soon as the clock is corrected; nothing gets locked out.
- Pairing doesn't need a watermark: each session is single-use, and its replay rows go when the session does.

**About the token.** It travels in a plain header and can be sniffed on the Wi-Fi. That's fine: it only
selects the device and gates revocation. The protection comes from the `sync_key`, which never appears in the
QR and is only ever sent encrypted under `shared` (§2.4). Someone who photographed the QR and recorded the
traffic still can't read or forge sync messages. An attacker who has the QR can only race to pair **their
own** device, or swap `phone_pub` so the real phone's pairing fails. Both are visible to the user and undone
with **Remove** (§2.5).

**No clock-offset retry.** On `clock_skew` the phone MUST NOT retry with `server_time` as an offset. If the
*computer's* clock had jumped forward, an offset retry would get accepted and push `W` ahead, locking the phone
out after the clock is fixed. The phone shows the clock message instead (§7.2). `server_time` is for the
"Details" line only.

### 4.5 Encoding plaintext

Python `json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`; TypeScript
`new TextEncoder().encode(JSON.stringify(obj))`. Either side MAY escape non-ASCII as `\uXXXX`; it decodes the same.

### 4.6 Strict base64url

Every binary field is base64url **without padding**. Decoders on both sides MUST:
1. accept only `^[A-Za-z0-9_-]*$` (no `=`, `+`, `/`, whitespace or newlines);
2. reject strings with `length % 4 == 1`;
3. reject non-canonical strings: re-encoding the decoded bytes MUST give back the exact input
   (e.g. `Zk3pR7tQ1xYb9mWc2nLs5a` is rejected; `Zk3pR7tQ1xYb9mWc2nLs5Q` is the canonical form of the same bytes);
4. check exact decoded lengths: nonce **24**, keys (`pair_pub`, `phone_pub`, `sync_key`) **32**,
   token **32**, code **16**, server_id **16**.

Server violations → 400 `bad_request`, including a malformed token in the `Authorization` header. On the phone,
a bad QR field → `invalid_qr` and a bad response field → `bad_response`.

Python:

```python
import base64
import re

_B64U = re.compile(r"[A-Za-z0-9_-]*")

def b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

def b64u_decode(s: str, expected_len: int | None = None) -> bytes:
    if not isinstance(s, str) or not _B64U.fullmatch(s) or len(s) % 4 == 1:
        raise ValueError("not base64url")
    b = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    if b64u_encode(b) != s:
        raise ValueError("non-canonical base64url")
    if expected_len is not None and len(b) != expected_len:
        raise ValueError("wrong length")
    return b
```

(Use `fullmatch`: `re.match(...$)` would accept a trailing newline.)

TypeScript (no Node `Buffer` in React Native; `tweetnacl-util` works in standard base64, so convert):

```ts
import { decodeBase64, encodeBase64 } from 'tweetnacl-util';

const B64U = /^[A-Za-z0-9_-]*$/;

export const b64uEncode = (b: Uint8Array): string =>
  encodeBase64(b).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

export function b64uDecode(s: string, expectedLength?: number): Uint8Array {
  if (typeof s !== 'string' || !B64U.test(s) || s.length % 4 === 1) throw new Error('not base64url');
  const std = s.replace(/-/g, '+').replace(/_/g, '/');
  const bytes = decodeBase64(std + '='.repeat((4 - (std.length % 4)) % 4));
  if (b64uEncode(bytes) !== s) throw new Error('non-canonical base64url');
  if (expectedLength !== undefined && bytes.length !== expectedLength) throw new Error('wrong length');
  return bytes;
}
```

### 4.7 Test vectors

Computed with PyNaCl 1.6.2 and cross-checked with tweetnacl 1.0.3 + tweetnacl-util (identical output, and the
helpers above accept/reject the same strings). Both sides SHOULD include these as unit tests. All keys and
nonces here are fixed **for tests only**; real ones are random. `bytes a..b` means consecutive byte values.

**Secretbox key** (bytes `0x00..0x1f`): `AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8`

**Vector 1: request** (nonce = bytes `0x20..0x37`)

- Inner plaintext (97 bytes UTF-8, exactly this string):
  `{"type":"req","ts":1790000000,"method":"POST","path":"/api/sync/snapshot","contract":1,"data":{}}`
- Envelope:

```json
{"v":1,"nonce":"ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3","ts":1790000000,"box":"h3tnJpseU-mZcMCYFrdbMYp7Odw9QnisK0cwHy5klYDKkIe6xiATRIxGA6LyN46Q0n-4rJ-LQ-3zIQDf1_FcItKiwusyFNue2TJQ6OB3Ly7bIX6xJfqbUjm4RRhuulXPJek3maWpfGGPCQ12_-DORKg"}
```

- `box` is 113 bytes; hex:
  `877b67269b1e53e99970c09816b75b318a7b39dc3d4278ac2b47301f2e649580ca9087bac62013448c4603a2f2378e90d27fb8ac9f8b43edf32100dfd7f15c22d2a2c2eb3214db9ed93250e8e0772f2edb217eb125fa9b5239b845186eba55cf25e93799a5a97c618f090d76ffe0ce44a8`

**Vector 2: response with non-ASCII text** (nonce = bytes `0x40..0x57`)

- Inner plaintext (135 bytes UTF-8; `é` is `c3 a9`):
  `{"type":"res","ts":1790000001,"re":"ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3","status":200,"data":{"merchant":"Café Olé","total_cents":1234}}`
- Envelope:

```json
{"v":1,"nonce":"QEFCQ0RFRkdISUpLTE1OT1BRUlNUVVZX","ts":1790000001,"box":"hlFMv8abBA-l4oJaaRR4wDE1IQBKNJkQ5CsUEkqleIW9FXxlWnpv-NTlEvrI9aEmsRZTM6f0g20QNU0Ve5s5QMvnTB_rzYAzxKj6ykod04XRmOGWeePezi-F5XD-bD8BYnJcPJt9bVe9XcBjvFOnpeuQUTyfJAe-DC--kT6NYdUvBUQi5_anPPrja69GQjnA3ZUMVuf2DQ"}
```

**Vector 3: tampering.** Flip the lowest bit of the last byte of vector 1's `box`; opening MUST fail
(PyNaCl raises `CryptoError`, tweetnacl returns `null`).

**Vector 4: pairing request (§2.4, §3.6)**

Secret keys load with tweetnacl `nacl.box.keyPair.fromSecretKey(sk)` and PyNaCl `PrivateKey(sk)`.

| Item | Value |
| --- | --- |
| `pair_sk` (server) | bytes `0xa0..0xbf` |
| `pair_pub` (in the QR) | `YFpyXSpK3-6xop4X7dYhwbdZPujNvESsbEq24vgF0jw` |
| `phone_sk` | bytes `0x80..0x9f` |
| `phone_pub` | `ST6C_HRGSlkmiBdiPSBTxeuOLMSpiLT-4XnsawENUx0` |
| `shared` (both sides) | `zSsDtyenL7oJQc53ndiVIG5KaKRYVTL4LHpaOqazn_c` (hex `cd2b03b727a72fba0941ce779dd895206e4a68a4585532f82c7a5a3aa6b39ff7`) |
| nonce | bytes `0xc0..0xd7` = `wMHCw8TFxsfIycrLzM3Oz9DR0tPU1dbX` |

- Inner plaintext (185 bytes UTF-8, exactly this string):
  `{"type":"req","ts":1790000000,"method":"POST","path":"/api/pair","contract":1,"data":{"code":"pQ3mX9vT2aLk8RzN1bWc4g","device_name":"Test Phone","platform":"ios","app_version":"1.0.0"}}`
- Envelope (`box` is `secretbox(plaintext, nonce, shared)`, 201 bytes):

```json
{"v":1,"nonce":"wMHCw8TFxsfIycrLzM3Oz9DR0tPU1dbX","ts":1790000000,"phone_pub":"ST6C_HRGSlkmiBdiPSBTxeuOLMSpiLT-4XnsawENUx0","box":"iX68iqmvSCofJGxoNa6ebGX424xYOa65Hp175w4pshg0QFxkfGk7IJSqHtBmtUmvZqsuM3uzkXYBVTevNr3Pt8LZmisOoF1RHF7bcQ1d01XIRobOmjXEr5AKOoJ9Gip52s6weSGEDbLZYnq9dE0HaO4Hb475qcwAQ_hrx_EpnEXBfJatjlr-W3-1-1XYBTtN9dOC9U12WfqBH76uDT23FI_1BTze3vUIbT3lBerNaXkQflETufHrnpuhaIUEeVvJzNi_A-2QmCAH"}
```

**Vector 5: base64url strictness.** MUST be rejected: `Zk3pR7tQ1xYb9mWc2nLs5a` (non-canonical),
`ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3=` (padding), `ICEiIyQlJicoKSorLC0uLzAxMjM0NTY+` (`+`), `AAAAA`
(length % 4 == 1), `ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3` followed by `\n`, and `AAECAwQFBgcICQoLDA0ODxAREhMUFRYX`
when a 32-byte key is expected (it's 24 bytes).

**Token hash:** `sha256("YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8")` =
`128a42f0efc787b4710881a27873ead95dfcf13a9dfbdf9ca1f2f0600ecb9407`.

---

## 5. Snapshot schema

### 5.1 TypeScript

```ts
type Cents = number;       // integer
type IsoDate = string;     // "YYYY-MM-DD"
type IsoDateTime = string; // "2026-10-02T18:30:00Z"

export interface Snapshot {
  contract: 1;
  server_id: string;
  generated_at: IsoDateTime;
  currency: string;               // ISO 4217, e.g. "USD"
  period: {
    month: string;                // "2026-10"
    start: IsoDate;               // first day of month
    end: IsoDate;                 // last day of month
    days_elapsed: number;         // including today
    days_in_month: number;
  };
  income: {
    expected_cents: Cents;        // this month's expected take-home (from paychecks)
    received_cents: Cents;        // take-home received so far this month
    last_paycheck: { pay_date: IsoDate; net_cents: Cents } | null;
  };
  budget: {
    target_cents: Cents;          // sum of group targets
    actual_cents: Cents;          // sum of group actuals
    groups: BudgetGroup[];        // always needs, wants, savings in that order
  };
  transactions: SnapshotTransaction[];
  accounts: SnapshotAccount[];
  tax: TaxSummary;
  settings: SyncSettings;
}

export interface BudgetGroup {
  group: 'needs' | 'wants' | 'savings';
  name: string;                   // display name, e.g. "Needs"
  target_cents: Cents;
  actual_cents: Cents;            // spent (needs/wants) or saved (savings) this month, >= 0 normally
  categories: BudgetCategory[];
}

export interface BudgetCategory {
  id: number;                     // valid as ReceiptUpload.category_id
  name: string;
  target_cents: Cents;            // 0 if no target set
  actual_cents: Cents;
}

export interface SnapshotTransaction {
  id: number;
  date: IsoDate;
  description: string;            // cleaned merchant/description, <= 100 chars
  amount_cents: Cents;            // negative = money out, positive = money in
  category_id: number | null;
  account_id: number;
}

export interface SnapshotAccount {
  id: number;
  name: string;                   // user's label, e.g. "Everyday checking"
  kind: 'checking' | 'savings' | 'brokerage';
  balance_cents: Cents;
  balance_as_of: IsoDate;
}

export interface TaxSummary {
  year: number;                   // current calendar tax year
  donations_total_cents: Cents;
  realized_gains: {
    short_term_cents: Cents;      // negative = loss
    long_term_cents: Cents;
    is_estimate: boolean;
  };
  deductions: { kind: string; label: string; amount_cents: Cents; is_estimate: boolean }[];
  disclaimer: string;             // plain-English "not tax advice, check with a pro" line
}

export interface SyncSettings {
  reminder_days_default: 1 | 2 | 3; // 2 unless changed on the dashboard
  reminder_days_allowed: [1, 2, 3];
}
```

Rules:
- `transactions`: last **60 days** up to and including today, newest first, at most **500**. No account
  numbers, notes, or raw bank memo fields.
- `accounts`: never includes account numbers or `last4`.
- `deductions[].kind` is a stable key (`medical`, `education`, `home_office`, `hsa`, `business`, `other`, …);
  `label` is the display text. The phone shows unknown kinds using `label`.
- `deductions[].amount_cents` is the **amount recorded** (what the user spent or imported in that kind),
  not the amount the tax rules allow. Floors, limits, itemizing vs. the standard deduction, and
  employee vs. self-employed rules are not applied. The phone labels this section "Possibly deductible
  expenses" and must not present it as tax saved.
- `is_estimate: true` means "the Home Base is missing something" (e.g. a sale without a cost basis); the
  phone shows a small "missing info" tag.
- An empty database still produces a valid snapshot (zeros, empty arrays, three empty groups).

Money rules (how the server fills the totals; the phone trusts them and never re-derives them from
`transactions`):
- `income.received_cents` (and `expected_cents`) count **take-home pay only**. Refunds, transfers between
  the user's own accounts, and balance adjustments are never income.
- Needs and wants `actual_cents` (group and category) are **net of refunds** in the same category, so a
  refund-heavy month can make them negative. They exclude transfers between the user's own accounts and
  balance adjustments.
- The savings `actual_cents` is money moved into savings this month **minus withdrawals**, so it can be
  negative when more came out than went in.
- `transactions` still lists transfers, refunds and adjustments as they happened (sign = direction of
  money); they are for display only.
- `accounts[].balance_cents` is the account balance. **Negative means money owed** (e.g. overdrawn
  checking). Any future debt kind (credit card, loan) follows the same rule: an amount owed is negative.

### 5.2 Example

```json
{
  "contract": 1,
  "server_id": "Zk3pR7tQ1xYb9mWc2nLs5Q",
  "generated_at": "2026-10-02T18:30:00Z",
  "currency": "USD",
  "period": { "month": "2026-10", "start": "2026-10-01", "end": "2026-10-31", "days_elapsed": 2, "days_in_month": 31 },
  "income": {
    "expected_cents": 520000,
    "received_cents": 260000,
    "last_paycheck": { "pay_date": "2026-10-01", "net_cents": 260000 }
  },
  "budget": {
    "target_cents": 520000,
    "actual_cents": 171245,
    "groups": [
      {
        "group": "needs", "name": "Needs", "target_cents": 260000, "actual_cents": 158000,
        "categories": [
          { "id": 1, "name": "Rent", "target_cents": 150000, "actual_cents": 150000 },
          { "id": 2, "name": "Groceries", "target_cents": 60000, "actual_cents": 8000 }
        ]
      },
      {
        "group": "wants", "name": "Wants", "target_cents": 156000, "actual_cents": 3245,
        "categories": [ { "id": 7, "name": "Eating out", "target_cents": 30000, "actual_cents": 3245 } ]
      },
      {
        "group": "savings", "name": "Savings", "target_cents": 104000, "actual_cents": 10000,
        "categories": [ { "id": 12, "name": "Emergency fund", "target_cents": 50000, "actual_cents": 10000 } ]
      }
    ]
  },
  "transactions": [
    { "id": 981, "date": "2026-10-02", "description": "Corner Cafe", "amount_cents": -3245, "category_id": 7, "account_id": 1 },
    { "id": 975, "date": "2026-10-01", "description": "Paycheck", "amount_cents": 260000, "category_id": null, "account_id": 1 }
  ],
  "accounts": [
    { "id": 1, "name": "Everyday checking", "kind": "checking", "balance_cents": 342150, "balance_as_of": "2026-10-02" },
    { "id": 2, "name": "Rainy day", "kind": "savings", "balance_cents": 1250000, "balance_as_of": "2026-09-30" }
  ],
  "tax": {
    "year": 2026,
    "donations_total_cents": 45000,
    "realized_gains": { "short_term_cents": -12000, "long_term_cents": 84000, "is_estimate": true },
    "deductions": [
      { "kind": "medical", "label": "Medical", "amount_cents": 23000, "is_estimate": false }
    ],
    "disclaimer": "These totals help you get ready for tax time. They aren't tax advice."
  },
  "settings": { "reminder_days_default": 2, "reminder_days_allowed": [1, 2, 3] }
}
```

---

## 6. Receipt upload schema

### 6.1 Image transport: inside the encrypted envelope

Receipt photos travel **base64url-encoded inside the encrypted envelope**, not as a multipart upload.

- ADR-0002 requires every sync payload to be encrypted. A multipart file part would need its own encryption
  (its own nonce, its own binding to the request and to the details JSON), which is a second crypto code
  path on both sides. One envelope format for everything is simpler and easier to review.
- The cost is ~33 % base64 overhead plus memory for one batch. The phone keeps that small by **re-encoding
  before queueing** with `expo-image-manipulator`: longest edge ≤ **1600 px**, JPEG quality **0.7**. That
  gives roughly 200–600 KB per receipt, readable for OCR. With ≤ 5 receipts per batch a request stays around
  1–4 MB, well inside the 12 MiB limit.
- **The phone strips EXIF** (location, device details). Re-encoding through the image manipulator drops
  it; the phone MUST NOT copy metadata across.
- **Server checks before decoding the full image:** decoded data ≤ 3 MiB; starts with the JPEG magic bytes
  `FF D8 FF`; pixel size read from the header (e.g. Pillow `Image.open` without `.load()`, plus
  `Image.MAX_IMAGE_PIXELS`) ≤ 4096 × 4096 and ≤ 16 megapixels. Only then decode. Failures make the item
  `rejected` (`image_too_large` / `image_invalid`).
- The server re-encrypts the image at rest with Fernet (ADR-0003) and never writes the plain image to disk.

### 6.2 `ReceiptUpload`

```ts
export interface ReceiptUpload {
  client_id: string;              // lowercase UUID v4, generated when the photo is taken; idempotency key
  captured_at: string;            // RFC 3339 with offset or Z, when the photo was taken
  merchant?: string | null;       // <= 100 chars
  total_cents?: number | null;    // integer >= 0
  category_id?: number | null;    // a BudgetCategory.id from the last snapshot
  note?: string | null;           // <= 500 chars
  tax_deductible: boolean;        // default false
  deduction_kind?: 'donation' | 'medical' | 'business' | 'other' | null; // used when tax_deductible
  image: {
    mime: 'image/jpeg';
    width: number;                // px, after downscaling
    height: number;
    data: string;                 // base64url JPEG bytes, EXIF stripped
  };
}
```

Example (image data shortened):

```json
{
  "receipts": [
    {
      "client_id": "3f1c9a0e-8b7d-4c2a-9e51-6d0b7a2f4c18",
      "captured_at": "2026-10-01T12:14:03-05:00",
      "merchant": "Corner Pharmacy",
      "total_cents": 2399,
      "category_id": 4,
      "note": "Allergy meds",
      "tax_deductible": true,
      "deduction_kind": "medical",
      "image": { "mime": "image/jpeg", "width": 1200, "height": 1600, "data": "_9j_4AAQSkZJRgABAQ..." }
    }
  ]
}
```

### 6.3 `ReceiptResult`

```ts
export interface ReceiptResult {
  client_id: string;
  status: 'accepted' | 'duplicate' | 'rejected';
  receipt_id?: number;            // accepted / duplicate: the server's receipt ID
  reason?: 'image_too_large' | 'image_invalid' | 'invalid_field'; // rejected only
  message?: string;               // plain English, rejected only
  warnings?: 'unknown_category'[]; // accepted, with category dropped
}
```

```json
{
  "results": [
    { "client_id": "3f1c9a0e-8b7d-4c2a-9e51-6d0b7a2f4c18", "status": "accepted", "receipt_id": 57 },
    { "client_id": "a0b9...", "status": "duplicate", "receipt_id": 41 },
    { "client_id": "c7d2...", "status": "rejected", "reason": "image_invalid",
      "message": "This photo couldn't be read. Please take it again." }
  ]
}
```

Rules:
- **Idempotency:** `client_id` is unique across the Home Base. If it already exists, the server stores
  nothing new and returns `duplicate` with the original `receipt_id` (first upload wins, even if the details
  differ). A retry after a dropped connection is always safe.
- `category_id` that doesn't exist (e.g. deleted since the last snapshot): accept, set category to none, add
  warning `unknown_category`.
- `tax_deductible: true` without `deduction_kind` → treat as `other`. Turning a `donation` receipt into a
  donation record is server-side logic (#11), not part of this contract.
- Phone: remove `accepted` and `duplicate` items from the queue. Keep `rejected` items, show the message
  on the receipt, and let the user retake or delete it.

---

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

---

## 8. Sync flow on the phone

When the user taps **Sync** (and once right after pairing):

1. `GET /api/health`. Fail → `server_unreachable`. `contract` < 1 or missing → `update_needed`.
2. Upload queued receipts in batches of up to 5, oldest first, one batch at a time. Update the queue after
   each batch, so progress isn't lost if a later batch fails.
3. `POST /api/sync/snapshot`. Check `server_id`, save the snapshot locally, record `last_sync_at = now`
   (phone clock), clear *needs attention*. **This is the moment a sync counts as successful.**
4. `POST /api/sync/ack` (best-effort; failures are logged, not shown).
5. Reschedule the reminder (§9). Show "Synced just now".

Receipts go before the snapshot so the snapshot already reflects them. If step 2 fails with
`server_unreachable`, stop; if only some items were rejected, continue to step 3.

---

## 9. Reminder logic (phone)

- **Setting:** "Remind me to sync every 1 / 2 / 3 days". Stored on the phone. Until the user picks one, use
  the last snapshot's `settings.reminder_days_default` (2 if none). Allowed values come from
  `reminder_days_allowed`.
- **When to schedule:** after every successful sync (§8 step 3), when the setting changes, and on app start.
  Each time, cancel all Budget Buddy reminders and schedule fresh ones with `expo-notifications`.
- **When it fires:** `due = last_sync_at + N × 24 h`. If `due` falls in quiet hours (21:00–09:00 local),
  move it to 09:00 the next morning. If `due` is already past, schedule it for the next non-quiet minute
  ≥ now + 1 minute.
- **Follow-ups:** also schedule the same reminder 1 and 2 days after `due` (same quiet-hours rule), then stop.
- **Text:** title "Time to sync Budget Buddy", body "When you're home, open the app and tap Sync." With queued
  receipts: "You have 3 receipts waiting. When you're home, open the app and tap Sync."
- **Permissions:** ask right after the first successful sync, with one line of explanation. If refused, the
  Sync screen still shows "Last synced 3 days ago".
- **Not paired:** no reminders.

---

## 10. Out of scope for v1

- Syncing away from home (no relay, by design, ADR-0002).
- Finding the computer if its IP address changes: v1 shows `server_unreachable` (or `bad_host`); re-pairing
  fixes it. Automatic discovery (mDNS) may come in a later contract.
- Editing budget data from the phone, multiple Home Bases per phone, phone-initiated unpairing.

---

## 11. Security requirements

A checklist for PR authors and the security-reviewer. Each item names the roadmap PR that owns it.

**Pairing (#14 server, #16 dashboard, #18 phone)**
- [ ] #14: Pairing code 16 B from a CSPRNG and a fresh X25519 pairing keypair per QR; QR holds only `pair_pub`; code stored as SHA-256; 10-minute expiry; one active session (§2.3).
- [ ] #14: Session claimed with one atomic conditional `UPDATE`; proceed only if exactly 1 row changed.
- [ ] #14: Wrong codes count toward 5; failed decrypts don't; per-IP limit of 10/min on `/api/pair` (429).
- [ ] #14: Pair envelopes keyed with `shared = Box(pair_sk, phone_pub).shared_key()`; `pair_sk` deleted when the session ends; a fresh random `sync_key` per device, sent only inside the `shared`-encrypted response (§2.4).
- [ ] #14: Token 32 B, stored as SHA-256 hex; `sync_key` encrypted at rest.
- [ ] #14/#16: Revoke deletes `sync_key` and `seen_nonces`; the row stays, marked revoked (§3.10).
- [ ] #16: "New phone paired: &lt;name&gt;" with **Remove** shown right away, plus the "Didn't pair a phone just now?" hint (§2.5).
- [ ] #16: QR payload served from a loopback-only route with `Cache-Control: no-store`; never in a URL; never logged.
- [ ] #18: Reject QR if `app`/`v`/lengths are wrong or `host` isn't a private/loopback/link-local IP (§2.1).
- [ ] #18: Fresh X25519 keypair per pairing attempt; `shared = nacl.box.before(pair_pub, phone_sk)`; check `type`/`re`/`server_id` on the response; drop `phone_sk` and `shared` afterwards.
- [ ] #18: Credentials (sync key, token) only in `expo-secure-store`; replaced only after a new pairing fully succeeds.

**Network surface (#14/#15 server, #16 dashboard)**
- [ ] #15: `Host` allowlist on every route (403 `bad_host`).
- [ ] #15/#16: Only `/api/health`, `/api/pair`, `/api/sync/*` answer LAN clients; everything else is loopback-only (403 `not_this_computer`), based on the socket peer, never on headers.
- [ ] #16: State-changing dashboard routes check `Origin` and a CSRF token (403 `bad_origin`).
- [ ] #15/#16: No `Access-Control-Allow-*` headers anywhere.
- [ ] #14: Once a device is paired, keep the LAN listener on; dashboard/guide tells users to allow **Private networks** only in the firewall.

**Envelope and replay (#15 server, #18–#21 phone)**
- [ ] #15/#18: Strict base64url decoding with exact lengths (§4.6); vectors 1–5 pass on both sides.
- [ ] #15: Verification order of §4.4: token checked before the body is read; ±300 s window; inner `type`/`ts`/`method`/`path` checked.
- [ ] #15: `seen_nonces` keyed on decoded nonce bytes with `UNIQUE(device_id, nonce)`; failed insert = replay; persisted; per-device watermark `W = max(W, accepted_ts − 600)`, advanced only by accepted requests, never by the server clock (§4.4).
- [ ] #18–#21: No clock-offset retry on `clock_skew` (§4.4).
- [ ] #15: Errors after the box opens are encrypted with status ≠ 200; `server_error` never includes exception text.
- [ ] #18–#21: Phone checks response `type == "res"` and `re`; nonces from `expo-crypto` via `nacl.setPRNG`; fail closed without a CSPRNG, never `Math.random`.
- [ ] #18–#21: Plaintext errors never wipe credentials, snapshot or queue (*needs attention* state, §7.2).

**Uploads (#15 server, #20 phone)**
- [ ] #15: Body limits while streaming: pair/snapshot/ack ≤ 16 KiB, receipts ≤ 12 MiB (413).
- [ ] #15: Per image: ≤ 3 MiB decoded, JPEG magic `FF D8 FF`, header pixel size ≤ 4096×4096 and ≤ 16 MP before full decode; stored encrypted, never as plain files.
- [ ] #20: Re-encode to ≤ 1600 px JPEG at quality 0.7, strip EXIF, ≤ 5 receipts per batch, `client_id` UUID v4.
