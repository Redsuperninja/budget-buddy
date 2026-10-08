Part of the [Sync API contract, v1](../sync-contract.md). Conventions and key names are in §1 there.

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
