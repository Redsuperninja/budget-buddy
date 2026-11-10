# ADR-0016: Bank-file import (OFX/QFX): our own small reader, the bank's IDs, balances and holdings

**Status:** Proposed, 2026-11-10 (roadmap 26). Builds on step 1 of [ADR-0006](0006-bank-connections.md).

## Context
CSV import guesses columns, dates and signs, and spots duplicates by a fingerprint of the row itself. Banks also
offer the OFX/QFX ("Quicken / Money") download, which says exactly what each field is, gives every transaction a
unique ID (`FITID`), the statement balance, and for brokerages the holdings. QFX is OFX with Intuit headers. Two
dialects exist: OFX 1.x (SGML: tags often have no closing tag) and OFX 2.x (XML).

## Decision (proposed)
1. **Our own tolerant tag reader** (`services/imports/ofx_parsing.py`), no new dependency, no XML library.
   It reads tags and values as text, so there are no entities, DTDs or external files to expand. This removes the
   usual XML attacks and the licence question. Same limits as CSV: 5 MB, 10,000 transactions; UTF-8 and
   Windows-1252; the `CHARSET` header is honoured only for those two.
2. **Money is exact:** amounts are read as decimal text into integer cents (never floats); more than two decimals,
   or anything unreadable, is a problem row, as in CSV. Dates are `YYYYMMDD[HHMMSS[.XXX][[offset:TZ]]]`; the date
   part is used as written and the time zone is ignored.
3. **The bank's ID is the duplicate check.** `import_fingerprint` becomes a hash of account + `FITID` (so no
   migration). A bank that reuses a `FITID` for a different amount is a known quirk: the row is flagged, not
   merged. CSV rows for the same purchase are not matched to OFX rows automatically; the preview says so.
4. **The file must match the account.** The account number in the file (`ACCTID`, only its last 4 digits are ever
   shown or stored) is compared with the account's saved last 4; a mismatch stops the import with a plain-English
   message. First import for an account asks the user to confirm and saves the last 4.
5. **Balances:** `LEDGERBAL` and its date are offered as "your bank says the balance was …" and feed the existing
   **Match your bank's balance** flow. Nothing is changed without a click.
6. **Brokerage files (`INVSTMTRS`):** `INVPOS` holdings are shown next to the user's own stock records through the
   existing positions comparison and never replace cost basis. `INVTRAN` buys, sells and income reuse the activity
   import's linking rules (stock trades, dividends, deposit sweeps).
7. **Same path as CSV after parsing:** preview then save, import history, auto-sort rules, dividend and transfer
   detection. Preview first, nothing saved until confirmed. Routes: `POST /api/local/accounts/{id}/ofx-import/preview`
   and `.../ofx-import` (this computer only, body is the file).
8. The dashboard's **Import files** page accepts `.ofx` and `.qfx` and picks the reader by content, not by name.

## Security
File parsing is the risk. The reader never evaluates, follows or expands anything; sizes are capped before parsing;
descriptions get the same hidden-character clean-up and formula guard as CSV; account numbers and the raw file are
never logged or kept (only the import-history line); test files are made up. `security-reviewer` checks the parser
and the account-match step; `finance-tax-expert` checks signs, balances and holdings math.

## Consequences
- No new dependency; about 250 lines for the reader, split from the import code.
- Banks' dialects vary; each step ships with made-up sample files in the shapes we've verified, and anything the
  reader doesn't understand is reported, never guessed.
- Matching an OFX transaction to an earlier CSV one is left out for now (see 3).
