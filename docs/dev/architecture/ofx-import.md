# Bank OFX/QFX import

Decision: [ADR-0016](../../adr/0016-ofx-import.md). Roadmap 26. **Built so far: 26-1, the reader.** No routes yet.

Code: `services/imports/ofx_parsing.py`. Tests: `tests/imports/test_ofx_parsing.py` with made-up files from
`tests/imports/ofx_helpers.py`.

## The reader (`parse_ofx(data: bytes) -> OfxFile`)
- A tag splitter, not an XML parser: it reads `<TAG>value` text, so OFX 1.x (SGML, no closing tags on leaf
  values) and 2.x (XML) go through the same code. Entities, DOCTYPEs and `&#...;` are left as text; only
  `&lt; &gt; &quot; &apos; &amp;` are undone.
- Reads bank (`STMTRS`) and credit card (`CCSTMTRS`) statements: account type and the last four characters of the
  account number (the full number is never kept), each transaction's `FITID`, posted date, amount in cents and
  description (`NAME` and `MEMO`, cleaned like CSV descriptions), and the ledger balance with its date.
- Amounts are exact decimal text to cents; a non-zero third decimal, a comma or anything else is a problem
  (`parse_amount`). Dates use the first eight digits; time and zone are ignored (`parse_date`).
- **Problem transactions** (bad amount, date, missing or repeated `FITID`) are left out and listed as
  "Transaction N was left out: ..." in `OfxFile.problems`; the rest of the file is still read. The route step
  (26-2) will stop or skip, as CSV does with `skip_invalid_rows`.
- **Stops the whole file** (`OfxError`, plain English): over 5 MB, over 10,000 transactions, over 50 accounts, over
  500,000 tags, no `<OFX>`, no statement, or a currency other than USD. At most 100 problem notes are kept.
- Numbers and IDs are strict (from the security review): ASCII digits only, at most 14 whole-dollar digits, a
  `FITID` of printable ASCII (no hidden characters), `last4` letters and digits only, and the account type one of the
  known OFX types.
- Text is decoded as UTF-8 (BOM allowed) or Windows-1252 (when the header says `CHARSET:1252`, or as a fallback).

## Next
26-2 routes and `FITID` duplicates; 26-3 balance; 26-4 brokerage `INVSTMTRS`; 26-5 dashboard and guide.
