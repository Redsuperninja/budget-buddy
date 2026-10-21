# ADR-0003: Encryption at rest

**Status:** Accepted, 2026-10-02

## Context
The Home Base stores bank, paycheck, and receipt data on a personal computer that could be shared, backed up
to a cloud drive, or stolen.

## Decision
- A random **master key** is generated on first run and stored in the OS credential vault via `keyring`
  (Windows Credential Manager / macOS Keychain / Secret Service). It is never written to disk in plaintext.
- **Receipt images** and **encrypted backups** use Fernet (AES-128-CBC + HMAC) with keys derived from the master key.
- **Sensitive DB columns** (account numbers, free-text notes) are encrypted with the same scheme.
- The data folder lives outside the repo and outside synced cloud folders by default.
- Whole-database encryption (SQLCipher) will be re-evaluated once its Python wheels are reliable on Windows.

## Consequences
- Copying the data folder alone doesn't expose receipts or sensitive fields.
- If the OS credential is lost (e.g., Windows reinstall), data is unrecoverable without an exported backup + its
  recovery phrase. The setup flow must make the user save a recovery phrase.

## Amendment (roadmap #4, 2026-10-02)
How this was built, where it differs from or adds to the decision above:
- **AES-256-GCM instead of Fernet.** Fernet can't bind a value to where it belongs. GCM's
  "associated data" lets each value carry its `table.column` (and each receipt file its ID), so
  a value copied into another column or a renamed file fails to decrypt instead of showing up in
  the wrong place. Keys are 256-bit, and every value gets a random 96-bit nonce.
- **One master key per data folder, never used directly.** HKDF-SHA256 derives separate keys for
  DB fields, files and backups. The vault entry name is a hash of the folder path.
- **Key fingerprint file.** A one-way fingerprint of the master key (`key-fingerprint`) sits in
  the data folder, so the app refuses to start rather than quietly making a new key when the
  vault entry is missing or doesn't match. The file is only the quick check (#26): without it,
  any row in `budget.db` still blocks making a new key, and a key or recovery phrase must
  decrypt one stored value before it is accepted (`app/crypto/key_check.py`).
- **Recovery phrase** = the master key as 64 Crockford Base32 characters (16 groups of 4) with
  a version byte and a 56-bit checksum. No word list to bundle. Shown and restored with
  `python -m app recovery-phrase show|restore`.
- **Encrypted columns:** `accounts.last4`, `receipts.image_path`, and every `notes` column.
  Merchant, description and amounts stay plain so they can be searched, sorted and summed.
- **What a copied data folder still reveals.** Account numbers, notes and receipt photos are
  encrypted. Amounts, dates, descriptions, shop, employer and charity names are **not**
  encrypted yet: every amount and date, `transactions.description`, `receipts.merchant`,
  `paychecks.employer` (with gross and net pay), `accounts.name`, `accounts.institution`,
  `donations.organization`, and stock symbols and lots. So keep the data folder out of
  cloud-synced folders and protect your Windows account. Encrypting more columns, or the whole
  database (SQLCipher or sqlite3mc), is tracked in #28. This narrows the first Consequence above:
  copying the folder doesn't expose receipts or the encrypted fields, but it does expose the
  plain ones.
- **Accepted limitation: a value is tied to its table and column, not its row.** The associated
  data is `table.column`, so swapping two rows' ciphertexts in the same column (for example two
  accounts' `last4`) still decrypts, just with the values swapped. Binding the row's primary key
  would need row context, which a SQLAlchemy `TypeDecorator` doesn't get. The impact is small:
  doing this needs write access to the database, and tampering or moving a value to another
  column is still caught.
- **Test-only memory key store.** `BUDGET_BUDDY_KEY_STORE=memory` keeps the key in the process
  only. It also needs `BUDGET_BUDDY_INSECURE_TEST_KEYSTORE=1`, and is refused on a folder that
  already has data or a `key-fingerprint`, so it can never take over real data.
- **Plain-text clean-up is retried.** Before the first encryption migration a `scrub-pending`
  marker is written. Each start then runs VACUUM and `wal_checkpoint(TRUNCATE)` while the marker
  exists, and removes it only once the checkpoint reports it wasn't busy. `secure_delete` is on,
  so deleted rows are zeroed rather than left in free pages.

## Update (#28, 2026-10-20)
The re-evaluation promised above is done: SQLCipher now has Windows, macOS and Linux wheels (`sqlcipher3` 0.6.2
and later) and works with SQLAlchemy and Alembic. [ADR-0014](0014-whole-database-encryption.md) proposes
encrypting the whole database with it and keeping the field encryption above. Until it is accepted and built,
the plain-text list above still applies.
