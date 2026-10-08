# Paychecks

> **Estimates, not tax advice.** Budget Buddy helps you keep your pay stubs organized and spot
> things worth a second look. Check your W-2 and the IRS instructions, tax software, or a tax
> professional before you file.

## What you enter

Copy each line from your pay stub. Amounts are whole cents, so `$2,500.00` is `250000`.

| Field | What it is |
| --- | --- |
| `pay_date` | The date you were paid (the "check date"), like `2026-01-15` |
| `employer` | Who paid you |
| `gross_cents` | Total pay before anything is taken out |
| `federal_tax_cents` | Federal income tax withheld |
| `state_tax_cents` | State income tax withheld |
| `social_security_cents` | Social Security tax (often "OASDI" on the stub) |
| `medicare_cents` | Medicare tax |
| `retirement_cents` | **Before tax:** traditional 401(k), 403(b) or 457 |
| `hsa_cents` | **Before tax:** HSA contributions taken from your pay |
| `health_insurance_cents` | **Before tax:** health, dental and vision premiums, FSA, and similar "Section 125" benefits |
| `roth_retirement_cents` | **After tax:** Roth 401(k) or Roth 403(b) |
| `other_deductions_cents` | **After tax:** anything else, such as union dues or after-tax insurance |
| `net_cents` | Take-home pay: what reached your bank |
| `notes` | Optional. Stored encrypted |

## It has to add up

Gross pay minus every tax and deduction must equal net pay, to the cent:

```
  2,500.00  gross
-   250.00  federal tax
-   100.00  state tax
-   155.00  Social Security
-    36.25  Medicare
-   150.00  401(k)
-    50.00  HSA
-    80.00  health insurance
-    50.00  Roth 401(k)
-    10.00  union dues
= 1,618.75  net
```

If it doesn't, Budget Buddy says how far off it is, for example *"net pay is $1.00 more than
gross pay minus all taxes and deductions"*, so you can find the line you missed. If your stub has
a line that doesn't fit any field, add it to the closest one of the same kind (before tax or
after tax) and mention it in the notes.

## Linking the bank deposit

You can link a paycheck to the deposit in your checking or savings account. The deposit must be
for exactly the net pay.

Your paycheck is **never counted as income by itself**. Income in your budget comes from your bank
transactions, so linking a paycheck to its deposit just explains where that money came from. It
is counted once, not twice. While they're linked, you can't change the paycheck's net pay or the
deposit's amount without removing the link first.

## Year-to-date summary

`GET /api/local/paychecks/summary?year=2026` adds up every paycheck paid in that year: gross pay,
each tax, each deduction, and net pay, plus totals for taxes, before-tax deductions and after-tax
deductions.

It also checks **Social Security**. Social Security tax is only charged on wages up to a yearly
limit ($184,500 in 2026, so at most $11,439.00 of tax). The numbers come from the tax-year files
(see [dev/tax-data.md](dev/tax-data.md)).

- **More than one job, too much in total:** each employer withholds on its own, so together they
  can take out more than the maximum. You can usually get the extra back as a credit on your
  federal tax return.
- **One employer took too much on its own:** that employer has to fix it. You can't claim it back
  on your tax return.

This check assumes every paycheck you entered is yours. The limit applies to each person, so if
you also enter a spouse's paychecks, the check isn't meaningful yet.

## Privacy

Employer names and amounts are stored as plain text so they can be added up (notes are
encrypted). They are never written to log files.
