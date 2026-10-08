Part of the [Sync API contract, v1](../sync-contract.md). Conventions and key names are in §1 there.

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
