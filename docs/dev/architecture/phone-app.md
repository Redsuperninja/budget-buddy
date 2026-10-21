# Phone app

Folder: `mobile/` ([mobile/README.md](../../../mobile/README.md) for running it, the file layout and dependencies).

- **Expo (React Native + TypeScript)** with expo-router. Runs on iPhone and Android inside Expo Go, so there is
  no app store and no custom native code.
- **Works offline.** It keeps the latest snapshot from the Home Base and a queue of receipt photos taken
  since. Until the first sync it shows a made-up sample snapshot with a banner saying so.
- **Screens:** Home (budget breakdown), Taxes summary, Settings (connect to the computer, **Sync now**), the
  pair screen (scan the QR or paste its text), and Add Receipt (camera, details form and the list of receipts waiting to sync; roadmap #20).
- **Talks to the Home Base only through the [sync contract](../../api/sync-contract.md)**, on home Wi-Fi.
  Pairing: [pairing.md](pairing.md). Syncing: [sync.md](sync.md).
- **Receipt queue** (`src/receipts/`, roadmap #20): receipts wait on the phone until a sync sends them (contract §6,
  §8 step 2, before the snapshot). The list is sealed in AsyncStorage (`budgetbuddy.receipts.v1`) and each photo is
  its own sealed file (`receipts/<client_id>.bin`, nonce then box), both with the phone-only cache key; only a UUID
  names a file. A photo must be a JPEG of at most 3 MiB (§6.1) and its ID new. Changes run one at a time and never
  save over a list that couldn't be read. Batches are 1-5 receipts under 11 MiB, sent with a 2-minute timeout; a
  photo is opened only for its own batch. Only answers about receipts actually sent count: `accepted`/`duplicate`
  delete the receipt and photo, `rejected` keeps it with the Home Base's message (cleaned like other server text,
  at most 200 characters) until you retake or delete it. A photo that won't open is marked to retake without
  being sent. An unreachable computer stops the sync; any other receipt problem leaves them queued and the sync
  goes on to the snapshot (§8). At app start (after the first screen is drawn), photo files no receipt lists are deleted, and so are the camera's and image
  manipulator's cache folders (`Camera`, `ImageManipulator`), in case a plain photo was left by an app that stopped
  mid-photo (`ReminderKeeper`). A photo is shrunk to 1600 px at JPEG 0.7 by re-encoding, which strips EXIF
  (`receipts/photo.ts`); its plain files are deleted at once and only the bytes are kept, sealed by the queue.
- **Reminders** (`src/sync/reminders.ts`, roadmap #21): local notifications only, following sync contract §9:
  every 1, 2 or 3 days (the snapshot's `reminder_days_default` until you pick; Off is a phone-only extra), due
  N days after the last sync and moved out of quiet hours (21:00-09:00) to 09:00, or the next non-quiet minute if
  overdue; two follow-ups 1 and 2 days later. All three are cancelled and made fresh after each sync, when the
  setting changes and when the app starts (`ReminderKeeper`); none when not paired. Permission is offered once
  right after the first successful sync (`ReminderOffer`) or asked when you pick a choice. The text is the
  contract's, with the waiting receipt count, never money. expo-notifications also ships push plumbing (Firebase
  Messaging on Android, the `aps-environment` entitlement on iOS); it stays off because the app never asks for a
  push token and has no Firebase config, and `src/__tests__/noPush.test.ts` fails if either appears. It adds two
  Android permissions: `POST_NOTIFICATIONS` and `RECEIVE_BOOT_COMPLETED` (so reminders survive a restart).
- **Storage:** keys and tokens in `expo-secure-store` only. The snapshot is in AsyncStorage, always encrypted
  (`src/sync/cacheCrypto.ts`, `snapshotDisk.ts`): `nacl.secretbox` with a fresh nonce each save and its own 32-byte
  key in secure store (`budgetbuddy.cache_key.v1`, `WHEN_UNLOCKED_THIS_DEVICE_ONLY`, so never in a backup), stored
  as `budgetbuddy.snapshot.v2` = `{"v":1,"n","c"}`. A copy that won't open counts as "nothing saved"; an older
  plain `budgetbuddy.snapshot.v1` is deleted as soon as it is read, then saved again sealed; saves run one at a time. No secure random source: nothing is saved.
  Android app backup is off (`app.json` `allowBackup: false`).

If the phone can't reach the Home Base it says so in plain words ("Make sure your computer is on and Budget
Buddy is running").
