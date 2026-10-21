# ADR-0014: Encrypt the whole database with SQLCipher

**Status:** Accepted by the owner, 2026-10-20 (issue #28, step 2), for 0.1.0. The security review's requirements
below are part of the build.

## Context
`budget.db` still holds every amount, date, description, shop, employer and charity in plain text
([ADR-0003](0003-encryption-at-rest.md), amendment). ADR-0003 put off whole-database encryption until its Python
wheels were reliable on Windows. Two ways were tried on 2026-10-20 (Windows 11, Python 3.14, SQLAlchemy 2.1.5,
Alembic 1.20.0, the versions in our lock file), each in a throwaway venv:

| | `sqlcipher3` 0.6.4 | `sqlcipher3-wheels` 0.5.7 | `apsw-sqlite3mc` 3.54.0.0 |
| --- | --- | --- | --- |
| Inside | SQLCipher 4.19 + OpenSSL 3.6, SQLite 3.53.4 | SQLCipher 4.12 + OpenSSL 3.6, SQLite 3.51.1 | SQLite3 Multiple Ciphers 2.6.1, SQLite 3.54 |
| Maintainer | Charles Leifer (also peewee); its own wheels since 0.6.2 (Jan 2026); 3 releases in 2026 | laggykiller, a one-person fork, "Beta"; last release Jan 2026 | Ulrich Telle (sqlite3mc's author) on Roger Binns's APSW; follows each SQLite release |
| Wheels, cp312-cp314 | win_amd64/arm64, macOS arm64 + x86_64, manylinux_2_28 x86_64/aarch64 | same, plus more Linux CPUs | same |
| Licence | zlib wrapper; SQLCipher BSD-3; OpenSSL Apache-2.0 | same | zlib (APSW), MIT (sqlite3mc), SQLite public domain |
| Works with SQLAlchemy | **Yes**: DB-API; `module=sqlcipher3.dbapi2`, Alembic batch migration ran | Yes (Alembic not tried) | **No**: APSW isn't DB-API (no `commit`, `rollback`, `create_function`); `create_engine(creator=...)` fails. Needs our own dialect |
| Raw 256-bit key (from HKDF) | `PRAGMA key = "x'<64 hex>'"`, no KDF | same | chacha20 runs PBKDF2 on any key (85 ms per open, or `kdf_iter=1`); its `sqlcipher` mode takes `x'..'` |
| Encrypt an existing file | `ATTACH ... KEY` + `sqlcipher_export()` (+ copy `user_version`) | same | `PRAGMA rekey` in place |
| Change the key | `PRAGMA rekey`, also in WAL mode | same | `PRAGMA hexrekey`, also in WAL mode |

All three passed: the db, `-wal` and `-shm` files had no plain marker text, no SQLite header and no schema text,
while open and after closing; a wrong key and Python's own `sqlite3` both got "file is not a database". Files are
interchangeable: SQLCipher opened a file from sqlite3mc's `sqlcipher` mode, and the other way round.

Rough speed (single runs): inserting 20,000 rows took 61 ms plain, 103 ms with `sqlcipher3`, 101 ms with
sqlite3mc; a full-table `LIKE` scan 2.6 → 3.8 ms; opening a connection 3.4 → 5.3 ms with a raw key, ~280 ms with
a passphrase (PBKDF2, 256,000 rounds). Fine for a one-person budget.

## Decision (proposed)
**Adopt SQLCipher through `sqlcipher3` (coleifer), and keep field-level encryption.** Not the `-wheels` fork
(older SQLCipher, one-person "Beta"); not sqlite3mc (no DB-API, so we'd own a SQLAlchemy dialect). sqlite3mc's
`sqlcipher` mode opens our files, so it stays the way out if `sqlcipher3` stops shipping wheels.
- **Key:** a new HKDF-SHA256 subkey of the master key (purpose `db-file`, info `budget-buddy/v1/db-file`), used as a raw key (no PBKDF2).
- **Backups (ADR-0012):** `VACUUM INTO` stays encrypted with the same key, so the staging folder no longer holds a
  plain database; restore opens the staged copy with the key derived from that backup's master key.

## Requirements for the build (from the security review of this ADR)
1. **The key never appears in SQL text, URLs or logs.** `hide_parameters` hides values, not statement text, so
   `PRAGMA key` runs only on the raw DB-API cursor inside the engine's `connect` listener, first; its hex string
   is built there and dropped (a Python string can't be wiped; the field keys are the same today). `ATTACH` uses
   a bound `KEY ?`. No `sqlite+pysqlcipher://` URL. A test checks that a failing connection's exception text and
   the logs hold no hex key. `PRAGMA cipher_log_level = NONE`.
2. **Every opener takes the key, and each gets an encrypted-database test.** Plain `sqlite3` today:
   `db.open_read_only`, `db.copy_database`, `db.database_revision`, `crypto.database_has_rows`,
   `backup/restore.py` (`_check_database`, `carry_over_removals`) and #26's `crypto/key_check.py`. A missed one
   does **not** always fail loudly: `database_has_rows`, `database_revision` and `_check_database` swallow
   `DatabaseError` and would quietly answer "has data", "no revision" or "corrupt".
3. **Opening with the database key is the key check (#26).** "File is not a database" under a key is reported as
   a wrong key, separately from "busy" (another copy open) and "corrupt".
4. **Restore:** `carry_over_removals` opens this computer's database with this computer's key and the backup's
   with the backup's key; if either fails, the restore stops, so a removed phone can't sync again. A backup from
   before SQLCipher is detected, exported to an encrypted file, and its plain staging copy deleted.
5. **Moving existing data, crash-safe, no plain copy kept:** write the `scrub-pending` marker, checkpoint the WAL,
   `sqlcipher_export` to a new file (with `user_version`), check it opens and its counts match, swap it in
   atomically, delete the plain `budget.db`, `-wal` and `-shm`, then clear the marker. A crash at any step resumes
   from the marker on the next start. Every older `budget.db.bak-*` is flagged as unencrypted, with deletion offered.
6. **Install wheels only** for `sqlcipher3` (`--only-binary`), so a missing wheel never builds from source against
   the system's OpenSSL. Add SQLCipher's BSD and OpenSSL's Apache-2.0 notices to
   `packaging/windows/THIRD-PARTY-NOTICES.txt` (the wheel carries only the wrapper's licence).
7. **OpenSSL age:** at start, refuse a `PRAGMA cipher_provider_version` below a minimum we set.

## Consequences
- A copied data folder reveals only file sizes. Step 1 of #28 (more encrypted columns) becomes optional.
- OpenSSL fixes arrive only with new `sqlcipher3` wheels, and Dependabot won't flag CVEs in the bundled copy. The
  exposure is small (AES, HMAC and the KDF on local files; no TLS); a long gap means switching to sqlite3mc.
- Opening `budget.db` with a plain SQLite tool no longer works; debugging needs the key.
- Not tested yet: macOS, Linux, Python 3.12 and 3.13 (only the wheels on PyPI were checked), a PyInstaller build,
  Budget Buddy's own code and test suite on SQLCipher (no app code was changed), and migrating a real-sized database.
  To repeat the experiment, see the commit that added this ADR.
