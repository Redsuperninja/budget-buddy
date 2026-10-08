# Sync API contract, v1

**Status:** Accepted (see [ADR-0004](../adr/0004-sync-contract-v1.md)) · **Contract version:** `1`

This is the single spec the Home Base (`server/`, roadmap #14, #15, #16) and the phone app (`mobile/`,
roadmap #18–#21) build against. If the two sides follow this document and pass the test vectors in §4.7, they
interoperate. Background: [ADR-0002](../adr/0002-wifi-qr-sync.md) (Wi-Fi + QR + secretbox) and
[ADR-0003](../adr/0003-encryption-at-rest.md) (encryption at rest). The short list of things each PR must
get right is in **§11, Security requirements**.

The words MUST, MUST NOT, SHOULD and MAY are used in their RFC 2119 sense.

## Sections

This page holds §1. The other sections are in their own files; section numbers never change, so a citation
like "§4.4" always means the same rule.

| § | Topic | File |
| --- | --- | --- |
| 1 | Conventions, keys and secrets | this page |
| 2 | Pairing: QR payload, session lifetime, key agreement, telling the user | [sync-contract/02-pairing.md](sync-contract/02-pairing.md) |
| 3 | Endpoints: network surface, headers, errors, each route, revoking | [sync-contract/03-endpoints.md](sync-contract/03-endpoints.md) |
| 4 | Encryption envelope: algorithm, request/response, verification order, base64url, test vectors (§4.7) | [sync-contract/04-envelope.md](sync-contract/04-envelope.md) |
| 5 | Snapshot schema and example | [sync-contract/05-snapshot.md](sync-contract/05-snapshot.md) |
| 6 | Receipt upload schema | [sync-contract/06-receipt-upload.md](sync-contract/06-receipt-upload.md) |
| 7 | Versioning and plain-English errors | [sync-contract/07-versions-and-errors.md](sync-contract/07-versions-and-errors.md) |
| 8–11 | Phone sync flow, reminders, out of scope, security requirements | [sync-contract/08-11-phone-flow-reminders-scope-security.md](sync-contract/08-11-phone-flow-reminders-scope-security.md) |

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
