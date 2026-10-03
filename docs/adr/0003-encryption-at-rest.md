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
  vault entry is missing or doesn't match.
- **Recovery phrase** = the master key as 64 Crockford Base32 characters (16 groups of 4) with
  a version byte and a 56-bit checksum. No word list to bundle. Shown and restored with
  `python -m app recovery-phrase show|restore`.
- **Encrypted columns:** `accounts.last4`, `receipts.image_path`, and every `notes` column.
  Merchant, description and amounts stay plain so they can be searched, sorted and summed.
