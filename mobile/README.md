# Budget Buddy phone app

The phone side of Budget Buddy, built with [Expo](https://expo.dev) (React Native + TypeScript) and
[expo-router](https://docs.expo.dev/router/introduction/). It runs inside the free **Expo Go** app on
iPhone and Android, so there's nothing to publish to an app store.

> Home and Taxes show a made-up **sample** budget (with a banner saying so) until you connect to your computer
> and tap **Sync now**. After that they show your real budget. Receipt photos come in a later update.

## Run it on your phone

1. Install **Expo Go** from the App Store (iPhone) or Google Play (Android).
2. On your computer (needs [Node.js](https://nodejs.org) 22 or newer):

   ```bash
   cd mobile
   npm install
   npx expo start
   ```

3. A QR code appears in the terminal.
   - **iPhone:** open the Camera app and point it at the QR code, then tap the banner to open in Expo Go.
   - **Android:** open Expo Go and tap **Scan QR code**.

Your phone and computer need to be on the same Wi-Fi network. If the phone can't connect, try
`npx expo start --tunnel`.

## Checks

```bash
npm run typecheck   # same as: npx tsc --noEmit
npm test            # Jest unit tests (jest-expo preset)
```

## Layout

| Path | What's there |
| --- | --- |
| `src/app/` | Screens. Each file is a route; `_layout.tsx` sets up the bottom tabs. |
| `src/components/` | Shared building blocks (screen wrapper, big button, card). |
| `src/theme.ts` | Colors (light + dark), spacing, font sizes. |
| `src/lib/money.ts` | `formatCents()`: turns integer cents into text like `$1,234.56`. |
| `src/lib/budget.ts` | Budget math for Home: percent used, left to spend, savings rate, on track / close / over. |
| `src/lib/dates.ts` | Plain-English dates ("October 2026", "2 days ago"). |
| `src/sync/snapshot.ts` | Snapshot types (sync contract §5) and `parseSnapshot()`, which checks a snapshot before use. |
| `src/sync/sampleSnapshot.ts` | Fictional sample snapshot shown until the phone has synced. |
| `src/sync/transport.ts` | Shared by pairing and syncing: secure random numbers, one HTTP request with a 10 s timeout, and the encrypted envelope (`sealRequest` / `openResponse`, contract section 4). |
| `src/sync/syncClient.ts` | `syncNow()`: health check, receipt-upload hook (#20), snapshot, save, best-effort ack. |
| `src/sync/runSync.ts` | Runs one sync for the screens (one at a time) and turns every outcome into plain English. |
| `src/components/SyncPanel.tsx` | The **Sync now** button and its status, on Home and Settings. |
| `src/sync/store.tsx` | `SnapshotProvider` / `useSnapshot()`: loads the saved snapshot, falls back to the sample. |

## Pairing (Settings, then Connect)

The pair screen (`src/app/pair.tsx`) connects the phone to the Home Base following the
[sync contract](../docs/api/sync-contract.md) (sections 2 and 3.6). It scans the QR code with the camera, or the
user can type or paste the code's text instead. Plain-English steps for users are in
[docs/guide/connect-your-phone.md](../docs/guide/connect-your-phone.md).

- **Secure storage:** the device token, sync key, and computer address are saved in `expo-secure-store`
  (`src/sync/credentials.ts`) only after the whole pairing succeeded. The phone's temporary pairing keys are
  never saved or logged.
- **Different computer:** if the phone is already connected and the new code is from another computer, the
  screen asks before replacing the connection. Cancel keeps the old one.
- **Web:** QR scanning is turned off on the web build (only typing the code works), so the scanner never loads
  code from the internet.
- Right after pairing succeeds the phone runs its first sync, so Home shows real data straight away.
- **Needs the computer side:** pairing and syncing can only be tried end to end once the Home Base endpoints
  (roadmap #14, #15) are running.

New dependencies for pairing:

| Package | Why |
| --- | --- |
| `expo-camera` | Scans the pairing QR code. |
| `expo-secure-store` | Keeps the token and sync key in the phone's secure storage. |
| `expo-crypto` | Secure random numbers for the pairing keys (no weaker fallback is ever used). |
| `expo-device` | The phone model name, used as the default name shown on the computer. |
| `tweetnacl`, `tweetnacl-util` | The encryption the contract specifies (pinned to exact versions). |

Pairing code lives in `src/sync/`: `pairingQr.ts` (checks the QR), `pairClient.ts` (the `/api/pair` call),
`pairErrors.ts` (plain-English messages), `credentials.ts`, `base64url.ts`.

## Syncing (Sync now)

Follows [sync contract](../docs/api/sync-contract.md) sections 3.5, 3.8, 3.9, 4, 7.2 and 8.

1. `GET /api/health` first, so "computer not reachable" is told apart from other problems.
2. (Hook only: receipt upload is roadmap #20. `SyncDeps.uploadReceipts` is where it plugs in.)
3. `POST /api/sync/snapshot`, encrypted with the sync key, `Authorization: Bearer <token>`, a fresh random nonce
   per request. The answer must open, be `type: "res"`, and have `re` equal to our nonce, or it is thrown away
   (`bad_response`). The snapshot is checked by `parseSnapshot()`, must carry this computer's `server_id`, and is
   only then saved. That moment counts as a successful sync.
4. `POST /api/sync/ack`, best effort; failures are not shown.

Safety rules: plaintext errors are unauthenticated, so they only show a message (and, for `not_paired`,
`device_revoked` and `decrypt_failed`, a **Pair again** button). They never delete the token, sync key or saved
snapshot. An encrypted `replay` answer is retried once with a new nonce. `clock_skew` is never retried with the
server's clock. Every request times out after 10 s (`AbortController`).

Further checks on every request: the saved address must still be a private or loopback IP with a valid port
(checked inside `transport.ts`, so the health check and pairing too); redirects are never followed; and the answer
size is capped (16 KiB, snapshot 2 MiB). A `Content-Length` over the cap is refused up front, and when the fetch
provides a streaming body the phone counts bytes as they arrive and aborts at the cap. **Limitation:** React
Native's built-in `fetch` may not stream, in which case the whole answer is read first and then measured in real
bytes (the 10 s timeout still applies). The health check must report `contract: 1`, otherwise the phone asks for
an update.

**Saved snapshot:** still kept in AsyncStorage (no keys in it), protected by the phone's lock. Encrypting it at
rest (issue #19) is not done here: secure-store has a small size limit, so it needs an encryption key in
secure-store plus an encrypted file. TODO for #19.

## Rules of the road

- Only use libraries that work in Expo Go (install with `npx expo install <package>`).
- Money is always integer cents; format it only when showing it.
- Keys and tokens go in `expo-secure-store` only, never in AsyncStorage or logs.
- Plain words, big buttons: the people using this aren't technical.
