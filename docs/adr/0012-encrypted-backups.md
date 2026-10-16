# ADR-0012: Encrypted backup files, unlocked by the recovery phrase

**Status:** Accepted, 2026-10-16 (roadmap 24).

## Context
Budget Buddy keeps everything in one data folder on one computer ([ADR-0001](0001-local-first-stack.md)). A dead
disk, a stolen laptop or a reinstalled Windows loses it all. [ADR-0003](0003-encryption-at-rest.md) promised "an
exported backup + its recovery phrase" as the way back, but there is no backup yet, and the recovery phrase can
only be seen from the command line. A backup file will be copied to USB drives and cloud folders, so it must be
encrypted as a whole: the database inside it has plain amounts and descriptions (ADR-0003, amendment).

| What unlocks a backup | On this computer | On a new computer | Weak point |
| --- | --- | --- | --- |
| **The recovery phrase (master key)** | Nothing to type | Type the phrase once | Losing the phrase (already true for the data itself) |
| A password chosen per backup | Type it | Type it | Weak or forgotten passwords; one per file |
| Both | | | Twice the code, tests and explaining |

## Decision
**A backup is one file encrypted with a key derived from the folder's master key** (the owner's choice).
- **Key:** HKDF-SHA256 from the master key's existing `backup` subkey, with a random 16-byte salt per file
  (info `budget-buddy/v1/backup-file`). A fresh key per file means nonces can never repeat across backups.
- **File** (`budget-buddy-backup-<date>.bbbackup`): a 36-byte plain header (`BBK`, version 1, the 16-byte
  key fingerprint, the salt; [backup.md](../dev/architecture/backup.md)) and then the contents in 1 MiB
  AES-256-GCM chunks. Each chunk's nonce is its number plus a "last chunk" flag, and every chunk authenticates
  the header, so a changed, reordered, cut-short or extended file fails to open.
- **Contents:** a tar stream of `manifest.json` (format, app version, database revision, counts), a consistent
  copy of `budget.db` (SQLite's backup API), `server-id` (so paired phones keep working) and every encrypted
  receipt file as it is. No keys, no logs, no lock or running files.
- **Restore checks everything first:** it decrypts the whole file into a staging folder inside the data folder,
  accepts only the expected names, runs SQLite's integrity check and refuses a database from a newer Budget
  Buddy. Only then does it swap: the current data moves to `before-restore-<date-time>/` in the data folder,
  never deleted, and migrations bring an older backup up to date on the next start.
- **Which key:** the fingerprint in the header says whose key made the file. If it is this folder's, nothing is
  typed. If not (a new computer), the person types the recovery phrase; it must match the file. A different key
  replaces this folder's only when this folder holds no data of its own, so restoring can't make other data
  unreadable.
- **Never while the Home Base runs.** A running Home Base holds an OS lock on the folder, which the swap must
  take. The command line refuses while it is running; the dashboard (24b) checks and stages the file, then
  finishes when Budget Buddy next starts, before the database is opened.
- **Removals stay removed.** Phones and computers removed since the backup was made are removed in the restored
  data too, so an old backup can't let a lost phone sync again.
- **Only encrypted-era data, without leftovers.** The database copy is made with `VACUUM INTO` (no free pages),
  and a database from before encryption isn't backed up.

## Consequences
- One secret for everything, and on the same computer backing up and restoring needs no typing at all.
- Losing the recovery phrase and the computer together still loses the data. The dashboard will show the phrase
  on this computer (24c), and the guide says to save it before relying on backups.
- A backup reveals its size, its date and which key made it (the fingerprint), nothing else.
- The staging folder briefly holds a plain database, with the same exposure as `budget.db` itself, in the same
  private folder; it is deleted after the swap or a failed check.
- Restore keeps the old data in `before-restore-*` folders that the person deletes when happy (the guide says
  how); Budget Buddy doesn't delete them by itself.
