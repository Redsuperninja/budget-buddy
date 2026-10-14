# Budget Buddy phone app

The phone side of Budget Buddy, built with [Expo](https://expo.dev) (React Native + TypeScript) and
[expo-router](https://docs.expo.dev/router/introduction/). It runs inside the free **Expo Go** app on
iPhone and Android, so there's nothing to publish to an app store. It talks to the Home Base only through the
[sync contract](../docs/api/sync-contract.md).

How it works: [phone-app.md](../docs/dev/architecture/phone-app.md), [pairing.md](../docs/dev/architecture/pairing.md)
(phone side) and [sync.md](../docs/dev/architecture/sync.md) (phone side).

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

More in [docs/dev/testing.md](../docs/dev/testing.md).

## Layout

| Path | What's there |
| --- | --- |
| `src/app/` | Screens. Each file is a route; `_layout.tsx` sets up the bottom tabs; `pair.tsx` is the pair screen. |
| `src/components/` | Shared building blocks (screen wrapper, big button, card, `SyncPanel.tsx` with **Sync now**). |
| `src/theme.ts` | Colors (light + dark), spacing, font sizes. |
| `src/lib/money.ts` | `formatCents()`: turns integer cents into text like `$1,234.56`. |
| `src/lib/budget.ts` | Budget math for Home: percent used, left to spend, savings rate, on track / close / over. |
| `src/lib/dates.ts` | Plain-English dates ("October 2026", "2 days ago"). |
| `src/lib/accounts.ts` | Account kind labels, "$50.00 owed" / "$12.00 credit" balances for cards and loans and "$30.00 overdrawn" for any other account below zero, the "need a category" and "need an app update" notes. |
| `src/sync/snapshot.ts` | `parseSnapshot()`, which checks a snapshot before use (re-exports the types). Accepts all account kinds (unknown kinds are skipped, but counted in the phone-only `skipped_accounts`, kept when the saved copy is checked again, so the accounts list can say "1 account needs an app update to show") and the optional `budget.unassigned`. |
| `src/sync/snapshotTypes.ts` | Snapshot types (sync contract §5). |
| `src/sync/snapshotChecks.ts` / `snapshotSections.ts` | Field checks, and the parser for each snapshot section. |
| `src/sync/sampleSnapshot.ts` | Fictional sample snapshot shown until the phone has synced. |
| `src/sync/transport.ts` | Shared by pairing and syncing: secure random numbers, one HTTP request with a 10 s timeout, and the encrypted envelope (`sealRequest` / `openResponse`, contract §4). |
| `src/sync/pairingQr.ts`, `pairClient.ts`, `pairErrors.ts`, `credentials.ts`, `base64url.ts` | Pairing: QR checks, the `/api/pair` call, plain-English messages, secure storage. |
| `src/sync/syncClient.ts` | `syncNow()`: health check, receipt-upload hook (#20), snapshot, save, best-effort ack. |
| `src/sync/runSync.ts` | Runs one sync for the screens (one at a time) and turns every outcome into plain English. |
| `src/sync/store.tsx` | `SnapshotProvider` / `useSnapshot()`: loads the saved snapshot, falls back to the sample. |

## Dependencies beyond Expo's defaults

| Package | Why |
| --- | --- |
| `expo-camera` | Scans the pairing QR code. |
| `expo-secure-store` | Keeps the token and sync key in the phone's secure storage. |
| `expo-crypto` | Secure random numbers for the pairing keys (no weaker fallback is ever used). |
| `expo-device` | The phone model name, used as the default name shown on the computer. |
| `tweetnacl`, `tweetnacl-util` | The encryption the contract specifies (pinned to exact versions). |

## Rules of the road

- Only use libraries that work in Expo Go (install with `npx expo install <package>`).
- Money is always integer cents; format it only when showing it.
- Keys and tokens go in `expo-secure-store` only, never in AsyncStorage or logs.
- Plain words, big buttons: the people using this aren't technical.
