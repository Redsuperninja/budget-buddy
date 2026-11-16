# Bank OFX/QFX import

Decision: [ADR-0016](../../adr/0016-ofx-import.md). Roadmap 26. **Built so far: 26-1 reader, 26-2 routes, 26-3 balance, 26-4a brokerage reader.**

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

## Statement balance (26-3)
The preview has `statement_balance: {balance_cents, date}` (the chosen statement's `LEDGERBAL`), or `null` when the file
has none. It is an offer only: importing never sets a balance; the user's click on **Match your bank's balance** posts it to the
existing `POST /accounts/{id}/balance` (`set_balance`), which stays the only writer. Code: `services/imports/ofx_balance.py`.
Signs: `set_balance` takes a card's owed amount as negative, and OFX writes it that way, so the number is offered as is.
With `flip_sign=true` the file is backwards throughout, so the balance flips too and matches the imported rows. While a
backwards-looking card file waits for the flip choice, the offer is `null`.

## Brokerage reader (26-4a)
Code: `services/imports/ofx_investments.py` (reader) and `ofx_invest_types.py` (dataclasses), tests `tests/imports/test_ofx_investments.py` (sample files in
`ofx_invest_helpers.py`). `parse_ofx` steps over `INVSTMTRS` for the bank reader (so a cash sweep's `STMTTRN` never lands
in a bank statement), then `read_brokerages` fills `OfxFile.brokerages` (one `OfxBrokerage` per account: `last4`,
`as_of`, `holdings`, `trades`, `income`, `cash`, `problems`). A file with only brokerage accounts is accepted by the
reader; the import routes refuse it with 422 `brokerage_not_supported` until 26-4b and 26-4c.
- **Holdings** (`POSSTOCK`, `POSMF`): ticker looked up from `SECLIST` by `UNIQUEID` (the list can come after the
  statement), units, unit price, market value in cents, and the price date (`DTPRICEASOF`, else the statement's `DTASOF`).
- **Lines:** `BUYSTOCK`/`BUYMF`/`SELLSTOCK`/`SELLMF` (`OfxTrade`: units, price, commission, fees, total, trade date,
  `FITID`), `INCOME` (`OfxIncome`: `DIV`, `INTEREST`, `CGLONG`, `CGSHORT`, `MISC`; the ticker is empty for cash
  interest; also `withholding_cents` and `tax_exempt`) and `INVBANKTRAN` cash sweeps (`OfxTransaction`, same as bank lines). `FITID` is unique per account.
- **Numbers:** money is integer cents; units and unit prices are integer **micro-units** (x 1,000,000; 6 decimals
  at most, a 7th non-zero digit is a problem line). Signs are as the file states them (sell units negative, buy total
  negative); 26-4c normalises them (below). A unit price with more than 6 decimals is rounded half away from zero to 6
  in `_price` (the `TOTAL` stays the authority). `parse_scaled` caps whole digits so values fit SQLite integers. `parse_scaled(text, decimals)` in `ofx_parsing.py` does the exact parse.
- **Left out, with a plain note:** options, bonds, other securities, margin interest, dividend reinvestments, returns
  of capital, splits, transfers, expenses, short sales and short positions, a line with no ticker or a bad number, date
  or `FITID`. Notes name no ticker, ID or amount. Same limits as the bank reader (5 MB, 10,000 lines, 50 accounts,
  500,000 tags, 100 notes, USD only).

- **Income kinds:** `CGLONG` and `CGSHORT` are a fund's capital-gain payouts (1099-DIV), not gains from selling shares.
- **Not dollars:** a line with its own `CURRENCY`/`ORIGCURRENCY` other than USD is left out, even in a USD file.
- **Later:** funds with no ticker (some 401(k) funds) are left out now; a name-based match may be needed.
- **26-4c must:** normalise signs by side; flag a trade whose |`TOTAL`| differs from units x price +/- costs by more
  than 1 cent; and block gains math for any security that has skipped lines (reinvestments, `SPLIT`, `RETOFCAP`,
  `TRANSFER` all change cost basis). Options stay left out.

## Next
26-4b holdings beside your own lots; 26-4c buys, sells and income through the activity rules; 26-5 dashboard and guide.
