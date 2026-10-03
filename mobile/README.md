# Budget Buddy phone app

The phone side of Budget Buddy, built with [Expo](https://expo.dev) (React Native + TypeScript) and
[expo-router](https://docs.expo.dev/router/introduction/). It runs inside the free **Expo Go** app on
iPhone and Android, so there's nothing to publish to an app store.

> Right now Home and Taxes show a made-up **sample** budget (with a banner saying so). Connecting to your
> computer, taking receipt photos, and syncing come in later updates; then these screens show your real budget.

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

## Rules of the road

- Only use libraries that work in Expo Go (install with `npx expo install <package>`).
- Money is always integer cents; format it only when showing it.
- Keys and tokens go in `expo-secure-store` only, never in AsyncStorage or logs.
- Plain words, big buttons: the people using this aren't technical.
