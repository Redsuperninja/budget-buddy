# ADR-0014: Encrypt the whole database with SQLCipher

**Status:** Proposed, 2026-10-20 (issue #28, step 2). Needs the owner's decision and a security review before it
is built.

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
**Adopt SQLCipher through `sqlcipher3` (coleifer), and keep field-level encryption.**
- `sqlcipher3`, not the `-wheels` fork: same API, newer SQLCipher and SQLite, the original maintainer. Not
  sqlite3mc: no DB-API means writing and owning a SQLAlchemy dialect. Its `sqlcipher` mode stays the way out if
  `sqlcipher3` stops shipping wheels; the files open there.
- **Key:** a new HKDF-SHA256 subkey of the master key (info `budget-buddy/v1/database`), passed as a raw key, so
  no PBKDF2. It is set first, in the engine's `connect` listener, before the other pragmas.
- **Every connection goes through SQLCipher.** Today `db.open_read_only`, `db.copy_database`,
  `backup/restore.py` and `crypto/__init__.py` use Python's `sqlite3`; they must take the key too. The backup API
  refuses a keyed-to-plain copy, so a missed spot fails loudly instead of leaking.
- **Moving existing data:** once, at start, before migrations: `sqlcipher_export` into a new file, check it
  opens and its counts match, then swap and delete the plain file and its `-wal`. Keep the `scrub-pending` idea:
  `budget.db.bak-*` copies and old free disk blocks may still hold plain data; the app says so.
- **Backups (ADR-0012):** `VACUUM INTO` keeps the database encrypted with the same key, so the file inside a
  backup is encrypted twice and the staging folder no longer holds a plain database. Restore opens the staged
  copy with the database key derived from that backup's master key (the same recovery-phrase path as now).
- **Build:** the lock files need no change in method: wheels exist for every OS we lock for. Add SQLCipher's BSD
  and OpenSSL's Apache-2.0 notices to `packaging/windows/THIRD-PARTY-NOTICES.txt` (the wheel carries only the
  wrapper's licence). Turn SQLCipher's stderr log off (`PRAGMA cipher_log_level = NONE`).

## Consequences
- A copied data folder reveals only file sizes. Step 1 of #28 (more encrypted columns) becomes optional.
- OpenSSL fixes reach us only when `sqlcipher3` publishes new wheels; Dependabot shows them, and a long gap
  means switching to sqlite3mc.
- Opening `budget.db` with a plain SQLite tool no longer works; debugging needs the key.
- Not tested yet: macOS, Linux, Python 3.12 and 3.13 (only the wheels on PyPI were checked), a PyInstaller build,
  Budget Buddy's own code and test suite on SQLCipher (no app code was changed), and migrating a real-sized database.
  To repeat the experiment, see the commit that added this ADR.
