# Phone app

Folder: `mobile/` ([mobile/README.md](../../../mobile/README.md) for running it, the file layout and dependencies).

- **Expo (React Native + TypeScript)** with expo-router. Runs on iPhone and Android inside Expo Go, so there is
  no app store and no custom native code.
- **Works offline.** It keeps the latest snapshot from the Home Base (and, once roadmap #20 lands, a queue of
  receipt photos taken since). Until the first sync it shows a made-up sample snapshot with a banner saying so.
- **Screens:** Home (budget breakdown), Taxes summary, Settings (connect to the computer, **Sync now**), the
  pair screen (scan the QR or paste its text), and Add Receipt (a "coming soon" placeholder until roadmap #20).
- **Talks to the Home Base only through the [sync contract](../../api/sync-contract.md)**, on home Wi-Fi.
  Pairing: [pairing.md](pairing.md). Syncing: [sync.md](sync.md).
- **Reminders:** a local notification when the last sync is older than the chosen interval (default 2 days,
  adjustable 1–3); rules in sync contract §9.
- **Storage:** keys and tokens in `expo-secure-store` only. The snapshot is in AsyncStorage, always encrypted
  (`src/sync/cacheCrypto.ts`, `snapshotDisk.ts`): `nacl.secretbox` with a fresh nonce each save and its own 32-byte
  key in secure store (`budgetbuddy.cache_key.v1`, `WHEN_UNLOCKED_THIS_DEVICE_ONLY`, so never in a backup), stored
  as `budgetbuddy.snapshot.v2` = `{"v":1,"n","c"}`. A copy that won't open counts as "nothing saved"; an older
  plain `budgetbuddy.snapshot.v1` is deleted as soon as it is read, then saved again sealed; saves run one at a time. No secure random source: nothing is saved.
  Android app backup is off (`app.json` `allowBackup: false`).

If the phone can't reach the Home Base it says so in plain words ("Make sure your computer is on and Budget
Buddy is running").
