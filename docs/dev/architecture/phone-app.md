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
- **Storage:** keys and tokens in `expo-secure-store` only; the snapshot in AsyncStorage (no keys in it).
  Encrypting the saved snapshot is issue #19.

If the phone can't reach the Home Base it says so in plain words ("Make sure your computer is on and Budget
Buddy is running").
