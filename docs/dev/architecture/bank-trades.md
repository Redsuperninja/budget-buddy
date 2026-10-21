# Stock trades in a bank file, and their deposit sweeps

Code: `services/investing/bank_trades.py` (find trades, link sweeps, remember tickers),
`services/investing/bank_trade_list.py` (the list with price per share, "not a trade"), `models/trades.py`,
`schemas/investing/bank_trades.py`, `routers/investing/bank_trades.py`. Dashboard: `screens/money/bank-trades-card.js` on Investments.
Checking sweeps by hand: `services/investing/sweep_check.py`, `routers/investing/sweep_check.py`,
`screens/money/sweep-check-card.js` (words in `sweep-words.js`).
Speed: the finders read thousands of rows, so they load them with `sweeps.lean()` (only id, account, date, amount, description; no notes, no linked rows) and sweeps are pre-filtered in SQL on "sweep". `scripts/dev/bench_reports.py` times them on made-up data.
User guide: [investments.md](../../guide/investments.md#stock-trades-from-your-bank-file).

Some brokers' bank-style files (J.P. Morgan / Chase) show a trade only as a line naming the company, with no ticker,
shares or price: `FAKECO UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A COMMISSION
EQUIVALENT - DETAILS ON REQUEST ROM`. Next to it a deposit sweep moves the same cash: `CHASE DEPOSIT SWEEP ...
INTRA-DAY WITHDRWAL` (money in) pays for a buy, `... INTRA-DAY DEPOSIT` (money out) parks a sale or a dividend.

## Routes (under `/stocks`, so joined computers and phones see them too)

- `GET /api/local/stocks/bank-trades`: newest first; date, account, `security`, `side` (`buy` = money out,
  `sell` = money in), `amount_cents`, `sweep_transaction_id`, and once recorded `symbol`, `shares_micro`,
  `price_cents` (amount / shares, rounded half up to the cent); `suggested_symbol` (the ticker you gave this
  company before, or one in brackets in the description).
- `POST /api/local/stocks/bank-trades/find`: look through every transaction (dividends first, so their sweeps go
  to them).
- `POST /api/local/stocks/bank-trades/{id}/dismiss`: not a trade; its sweep is freed; never found again. Refused
  (409 `trade_recorded`) once a purchase or sale is recorded from it: delete that instead.
- `GET /api/local/stocks/sweeps`: every free sweep line (any account; `sweeps.candidates`), newest first, each
  with `matches`: dividends and trades still without a sweep that it `fits`, smallest `gap_cents` first, then
  the closest dates (`exact`, `days_apart`); and `accounts`: per account, how
  many dividends and trades (`payments`), how many have a sweep (`with_sweep`), and `free_sweeps`.
- `POST /api/local/stocks/sweeps/{sweep_id}/link` with `{kind: "dividend"|"trade", record_id, confirm}`: link
  by hand, marked `sweep_by_hand`. The sweep's whole amount then leaves the budget, so it must be the same money
  (`fits`), or 409: `other_account` (a sweep in another account is real money moving between accounts),
  `same_direction`, `too_far` (more than 14 days apart), `too_different` (amounts more than $1 or 1% apart,
  whichever is more). Any gap needs `confirm: true` (409 `confirm_gap`); the page asks first, naming the gap
  that won't be counted anywhere. Also 409 `not_free` (already linked, not a free sweep line, or a dividend's own
  payment), `dismissed`, and `has_sweep` (the dividend or trade, or the line, was linked meanwhile: the update
  is guarded on both).
- `POST /api/local/stocks/sweeps/{sweep_id}/unlink`: frees it from every dividend and trade (`free_sweep`); 404
  if nothing has it. The page offers it as Undo right after a Link. A link the finders made comes back the next
  time they run, so a wrong one of those is fixed with "not a trade" / "not a dividend".
- Recording uses the Stocks API (`POST /stocks/lots` or `/stocks/sales` with `transaction_id`); that also saves the
  company's ticker (`security_symbols`). Bank CSV import results gain `trades_found` and `trade_sweeps_linked`.

## Tables (migrations 0025, 0026, 0027)

`bank_trades`: `transaction_id` (unique, `ON DELETE CASCADE`), `sweep_transaction_id` (indexed, not unique since
0026: several trades and dividends can share one sweep; `ON DELETE SET NULL`), `sweep_by_hand` (0027: linked by you; Match everything again leaves it, and Unlink clears it), `security` (from the description), `dismissed`. Date, amount and account are the transaction's.
`security_symbols`: `security` (unique) to `symbol`.

## Rules

- **When:** after a bank file or brokerage activity file is imported, after a transaction is added by hand, and on
  `find`; always after dividends.
- **A trade** is a regular transaction (not a transfer, paycheck deposit or donation) in a brokerage, retirement or
  HSA account whose description has trade-confirmation wording (acting as principal/agent, (un)solicited,
  commission field/equivalent), or a plain bought/sold without money market, MMKT, redemption, maturity or "to
  cover" words; and isn't a sweep, a dividend, or a cancel/correction/reversal/rebill/adjustment (a reversal
  would otherwise look like the opposite trade).
- **A trade you recorded yourself** (a stock purchase or sale linked to a regular transaction in an investment
  account, from the Transactions page or an activity file) becomes a `bank_trades` row too, but only once its
  sweep is found; without one it isn't listed. Every `find` run looks at all of them, so a sweep imported later
  is still linked, and recording a purchase or sale from a transaction runs `find` for it. Deleting that purchase
  or sale drops the row again if the description has no trade wording (`forget_recorded`), so the payment and
  its sweep count like any others.
- **Sweeps** are picked by `services/investing/sweeps.py`, shared with dividends: a trade is never a sweep.
- **Price per share** is the amount (commission included) / shares: cost basis on a buy, net proceeds on a
  sale. Shown as "with fees", since it can differ from the trade price.
- **Its sweep:** the opposite amount, same account, from 1 day before to 3 days after, "sweep" in the description,
  not already a dividend's or another trade's (dividends also skip trades' sweeps). Closest date, then first added.
- **One sweep for several:** after that, a free sweep is linked to a group of two or more trades and dividends still
  without one, same account and window, whose amounts add up to exactly its opposite: smallest group, then oldest
  payments; skipped with more than 10 waiting nearby (`services/investing/combined_sweeps.py`). "Not a trade" on one member
  frees the sweep from the whole group.
- **Budget:** a trade and its sweep are cash turning into shares (or back) inside the account, so the monthly
  summary, "needs a category", transfer matching and "hide dividends" leave both out. A dividend's linked sweep is
  also left out of "needs a category" and the monthly summary ([dividends.md](dividends.md)).
- **Company name:** the description without a leading bought/sold, up to "unsolicited", "we are acting", "common
  stock", "commission", "@", "(" or a digit.
- Not handled: share counts or prices in the description (they are typed once per trade), partial fills split
  across lines, and fees shown on separate lines.
