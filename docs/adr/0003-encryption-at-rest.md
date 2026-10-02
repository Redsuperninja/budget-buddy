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
