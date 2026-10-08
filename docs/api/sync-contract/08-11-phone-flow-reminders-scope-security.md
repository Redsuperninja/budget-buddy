Part of the [Sync API contract, v1](../sync-contract.md). Conventions and key names are in §1 there.

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
