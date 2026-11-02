# Backups

Why it works this way: [ADR-0012](../../adr/0012-encrypted-backups.md). Code: `server/app/crypto/stream.py` (the
encryption), `server/app/backup/archive.py` (what's inside), `server/app/backup/restore.py` (checking and swapping),
`server/app/cli_backup.py` (the commands).

## The file

`budget-buddy-backup-<date>.bbbackup` (the time is added if that name is taken):

| Part | Bytes | What |
| --- | --- | --- |
| Magic, version | 4 | `BBK`, `0x01`. A newer version is refused with "made by a newer Budget Buddy". |
| Key fingerprint | 16 | Which master key made it (the non-secret fingerprint from `app/crypto/keys.py`) |
| Salt | 16 | Random per file. File key = HKDF-SHA256(backup subkey, salt, `budget-buddy/v1/backup-file`) |
| Chunks | rest | Each 1 MiB of contents (the last shorter, maybe empty) as AES-256-GCM, 16-byte tag each |

A chunk's nonce is its number (11 bytes, big-endian) and a "last chunk" flag byte; the associated data is the
whole 36-byte header. A reader looks one chunk ahead to know which is last, so a file cut at a chunk boundary, with
anything appended, with chunks reordered or with a changed header fails to open.

## Inside

A tar stream (written and read in streaming mode, never whole in memory), in this order:

| Name | What |
| --- | --- |
| `manifest.json` | `format` (1), `app_version`, `database_revision`, `created` (Unix seconds), `receipts` (count). Always first. |
| `budget.db` | A consistent copy made with `VACUUM INTO` (includes the WAL; no free pages, so deleted or pre-encryption plain text never travels). A database from before encryption (revision < 0003) isn't backed up. |
| `server-id` | The Home Base's ID, so phones paired before keep working after a restore |
| `receipts/<32 hex>.bbf` | Each receipt photo exactly as stored (already encrypted with the files subkey) |

Never inside: the key or its fingerprint file, lock files, `home-base-running.json`, old `budget.db.bak-*` copies.

## Restoring

1. **Which key.** If the header's fingerprint is this folder's key, use it. Otherwise ask for the recovery phrase,
   which must match the header. A key other than the folder's is only accepted when the folder has no data of its
   own (no rows, no receipt files), so a restore can't make data unreadable.
2. **Check everything** into `<data folder>/.restore-<random>/`: decrypt every chunk, accept only the names above
   (plain files only, each once, manifest first, size limits for the manifest, `server-id` and receipts), then
   SQLite's `integrity_check` and a recorded database revision this version knows. Any failure (or Ctrl+C) deletes
   the staging folder; nothing else has changed. Staging folders and temporary copies an hour old or more are swept
   at start-up, in case one was cut short. "Data of its own" also counts earlier `before-restore-*` folders and
   `budget.db.bak-*` copies, since they need the folder's current key.
3. **Swap**, only while no Home Base runs on the folder. A running Home Base holds an OS lock on
   `home-base.lock` from start-up to shut-down (`app/run_lock.py`); the swap takes it (and `budget.db.lock`, which a
   starting Home Base holds while it migrates) and also checks `home-base-running.json`. Then:
   - phones and computers removed in the current data are removed in the restored database too (matched by
     token hash, and by ID and pairing time), so restoring an older backup can't let a lost phone sync again;
   - `budget.db` and its `-wal`/`-shm`, `server-id` and `receipts/` move into a new `before-restore-<date-time>/`
     with a copy of the old `key-fingerprint` (which recovery phrase opens it), and the staged files move in;
   - if a move fails, each move made so far is undone; if an undo fails too, nothing is deleted and the message
     lists what to move back by hand.
   The key goes into the password vault after the swap. Migrations bring an older backup up to date on the next
   start.

## Commands

```
python -m app backup make [--to FOLDER]     # default: Documents (or the home folder)
python -m app backup restore FILE           # Budget Buddy must be closed; asks RESTORE before replacing data
```

`make` works while the Home Base runs.

## In the dashboard (Devices → Backups)

Routes in `server/app/routers/backup.py`, this computer only (not on the other-computers allow-list); page in
`dashboard/js/screens/devices/backups.js`.

| Route | Does |
|---|---|
| `GET /api/local/backup` | Status: this folder's key fingerprint, a waiting restore, and where replaced data went (only on the start that finished one) |
| `GET /api/local/backup/file` | Makes a backup in the data folder (`.backup-*`), sends it, then deletes it |
| `POST /api/local/backup/restore` | Upload (limit 4 GB), checked in full like the command line, then left waiting; `X-Recovery-Phrase` for another key's backup |
| `DELETE /api/local/backup/restore` | Cancels a waiting restore (and drops its waiting key) |
| `POST /api/local/backup/recovery-phrase` | The folder's phrase, read from the vault each time (never kept in the running Home Base), `Cache-Control: no-store`; a POST so it needs the CSRF token |
| `GET /api/local/setup` | First-start setup progress (ADR-0015): `finished_at`, `phrase_saved_at`, `last_backup_at` (dates or null) |
| `PUT /api/local/setup` | Body `{finished?: bool, phrase_saved?: bool}` (unknown fields refused): true stamps the time once, false clears it. `last_backup_at` can't be sent: the server sets it when a backup file is written (`record_backup` in `services/setup_progress.py`, called by the dashboard download and `backup make`) |

The page reads the fingerprint from the file's first 36 bytes in the browser (`backup-words.js`) and asks for the
phrase only when it differs from the folder's. `app/backup/pending.py` swaps a waiting restore in at the next
start, before keys and the database are opened; another computer's key waits in the vault under its own name
until then.

Crash safety: before moving anything, the start renames `restore-pending.json` to `restore-swapping.json`, and
deletes it only after the key is stored. A start that finds it either finishes the last steps (the swap got to
the end: `restore-pending/` is gone) or stops with a plain message (cut off mid-swap), never swapping twice.
The download refuses a cross-site request (`Sec-Fetch-Site`), since a GET carries no CSRF token, and deletes its
copy even if the browser stops early. One restore upload is checked at a time.
