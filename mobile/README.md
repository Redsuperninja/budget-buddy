# Budget Buddy phone app

The phone side of Budget Buddy, built with [Expo](https://expo.dev) (React Native + TypeScript) and
[expo-router](https://docs.expo.dev/router/introduction/). It runs inside the free **Expo Go** app on
iPhone and Android, so there's nothing to publish to an app store.

> Right now Home and Taxes show a made-up **sample** budget (with a banner saying so). You can pair the
> phone with your computer (see below), but the computer side isn't built yet. Receipt photos and syncing
> come in later updates; then these screens show your real budget.

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
- **Not built yet:** the computer-side pairing server and dashboard button (other roadmap items), and the first
  sync after pairing. Pairing can't be tried end to end until those exist.

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

## Rules of the road

- Only use libraries that work in Expo Go (install with `npx expo install <package>`).
- Money is always integer cents; format it only when showing it.
- Keys and tokens go in `expo-secure-store` only, never in AsyncStorage or logs.
- Plain words, big buttons: the people using this aren't technical.
