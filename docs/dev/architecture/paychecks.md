# Paychecks and income (no double counting)

Code: `services/tax/paychecks.py`, `schemas/tax/paychecks.py`, `routers/tax/paychecks.py`. Estimates, not tax advice.
User guide: [docs/guide/](../../guide/).

## Fields

Amounts are whole cents, all ≥ 0.

| Field | What it is |
| --- | --- |
| `pay_date` | The date paid (the stub's "check date"); decides the tax year |
| `employer` | Who paid (plain text so it can be totalled; never logged) |
| `gross_cents` | Total pay before anything is taken out |
| `federal_tax_cents`, `state_tax_cents` | Income tax withheld |
| `social_security_cents`, `medicare_cents` | FICA (Social Security is often "OASDI" on the stub) |
| `retirement_cents` | **Before tax:** traditional 401(k), 403(b) or 457 |
| `hsa_cents` | **Before tax:** HSA contributions taken from pay |
| `health_insurance_cents` | **Before tax:** health, dental, vision premiums, FSA and similar Section 125 benefits |
| `roth_retirement_cents` | **After tax:** Roth 401(k) or Roth 403(b) |
| `other_deductions_cents` | **After tax:** anything else, such as union dues |
| `net_cents` | Take-home pay: what reached the bank |
| `account_id`, `deposit_transaction_id` | Optional deposit link (below) |
| `notes` | Optional, encrypted |

## It has to add up

`gross - (federal + state + social_security + medicare) - (retirement + hsa + health_insurance)
- (roth_retirement + other_deductions) = net`, in whole cents, or the API answers 422 `net_mismatch` with the
difference (e.g. "net pay is $1.00 more than gross pay minus all taxes and deductions"). Worked example:
2,500.00 gross − 250.00 − 100.00 − 155.00 − 36.25 − 150.00 − 50.00 − 80.00 − 50.00 − 10.00 = 1,618.75 net.

## Income is counted once

**Income in budget totals comes only from bank transactions. A paycheck is never counted as income by itself.**
Linking a paycheck to its deposit (`deposit_transaction_id`) only explains that deposit, so the money is counted
once: as the deposit. An unlinked paycheck adds nothing to income either; its money shows up when the deposit is
entered or imported. Paychecks feed the tax side (wages and withholding by tax year, by `pay_date`) and the
"expected take-home" estimate (the phone's `income.expected_cents`), never "received".

## Deposit link rules

- The deposit is a regular (`normal`) transaction of exactly `+net_cents` in a checking or savings account, and
  one deposit backs at most one paycheck (`deposit_transaction_id` is unique).
- While linked, the paycheck's net and account and the deposit's amount, account and kind are locked (409), and
  the deposit can't become half of a transfer.
- Deleting either side just removes the link.

## Routes (this computer only)

- `GET/POST /api/local/paychecks` (filter: `year`), `GET/PATCH/DELETE /api/local/paychecks/{id}`. Amounts are
  whole cents only (no dollar text).
- `POST/DELETE /api/local/paychecks/{id}/deposit` links or unlinks the bank deposit. `POST /api/local/paychecks`
  can also take `deposit_transaction_id` to add and link in one go (same checks; nothing is saved if they fail).
- `GET /api/local/paychecks/deposits?year=` (`services/tax/pay_deposits.py`): pay deposits no paycheck explains yet,
  newest first, at most 100: `normal` money in, not a transfer, in a checking or savings account, that's either
  in an income category with the word pay, paycheck, payroll or salary in its name, or has no category and a
  payroll word in its description (payroll, direct dep, dir dep, salary, paycheck, wages). Tax refunds, Social
  Security, unemployment and reimbursements (tax ref, irs, treas, ssa, unemploy, reimb) and anything in a
  non-income category are never offered. A pay split across two accounts can't be linked (one deposit must equal
  the net pay), so both halves stay listed. Each has an `employer` guess (the description up to the payroll word).
  The Paychecks page lists them; **Fill in** starts the form with the date, employer and take-home pay.
- `GET /api/local/paychecks/summary?year=2026`: year-to-date totals.

## Year-to-date summary

Adds up every paycheck paid in that year: gross, each tax, each deduction and net, plus totals for taxes,
before-tax deductions and after-tax deductions.

It also checks **Social Security** against that year's wage cap from the tax-year file (`fica`;
[../tax-data.md](../tax-data.md)):

- **Several employers, too much in total:** each employer withholds on its own, so together they can exceed the
  maximum. The extra can usually be claimed back as a credit on the federal return.
- **One employer took too much on its own:** that employer must fix it; it can't be claimed on the return.

The check assumes every paycheck entered belongs to one person. The cap is per person, so entering a spouse's
paychecks makes it meaningless (not handled yet).
