# Tax-year reference data

> **Estimates, not tax advice.** Budget Buddy uses these numbers to organize your records and give
> rough estimates. Tax rules have many exceptions that depend on your situation. Before you file,
> check with the official IRS instructions, tax software, or a tax professional.

## What this is

Every year the IRS changes many dollar limits: the standard deduction, the tax brackets, how much
you can put into an HSA or 401(k), and so on. Budget Buddy keeps all of those numbers in one file per
tax year, instead of scattering them through the code:

```
server/app/tax_data/2025.json
server/app/tax_data/2026.json
```

The code reads them with `load_tax_year(2026)` (in `server/app/tax_data/__init__.py`), which checks
each file against a strict schema when it loads.

## What's in each file

| Section | What it holds |
| --- | --- |
| `standard_deduction` | Basic amount for each filing status, plus the extra amount for age 65+ or blind |
| `senior_deduction` | The extra $6,000 deduction for people 65+ (2025–2028) and where it starts to phase out |
| `ordinary_brackets` | Income tax brackets for each filing status |
| `capital_gains_brackets` | Where the 0%, 15%, and 20% long-term capital gains rates start |
| `net_investment_income_tax` | The 3.8% tax on investment income and its income thresholds |
| `capital_loss_deduction_limit` | How much net capital loss can reduce other income each year ($3,000) |
| `charitable` | Limits as a share of income, paperwork thresholds ($250, $500, $5,000), the 2026+ deduction for people who don't itemize, and the 2026+ 0.5% floor |
| `hsa` | HSA contribution limits (self-only, family, age 55+ catch-up) |
| `retirement` | 401(k) and IRA contribution limits, including catch-up amounts |
| `salt_cap` | The cap on deducting state and local taxes and how it shrinks at high incomes |
| `student_loan_interest` | The $2,500 maximum and its income phase-out range |
| `medical_expense` | Medical costs count only above 7.5% of income |
| `fica` | Social Security and Medicare rates, the Social Security wage cap, and the Additional Medicare Tax |

The donations summary (`/api/local/donations/summary/{tax_year}`, roadmap #11) reads the
`charitable` paperwork thresholds and `non_itemizer_deduction_cents` from these files, and its
messages show the amounts from the file. Changing a threshold here changes the donation flags; no
code change is needed. If `non_itemizer_deduction_cents` is `null`, the summary leaves out the note
for people who don't itemize.

Each file also has `tax_year`, `last_reviewed` (the date someone last checked it against the IRS),
and a `sources` list. Every section names the sources that back it in `source_ids`, and may have a
`note` explaining anything unusual.

### Rules the files follow

- **Money is whole cents.** `$15,750` is written `1575000`. Field names end in `_cents`.
- **Rates are exact decimals** like `0.22`. The loader reads them as `Decimal`, never as floats.
- **Brackets** are listed lowest to highest. Each one covers income *up to and including*
  `up_to_cents`. The top bracket has `up_to_cents: null`, meaning "no upper limit".
- **`null` means "doesn't apply this year" or "couldn't be verified"**, and the section's `note`
  must say which. For example, the deduction for people who don't itemize is `null` in 2025 because
  it starts in 2026. We never guess a number.
- **Sources are primary.** Prefer IRS Revenue Procedures, Notices, publications, and form
  instructions on irs.gov.

## Adding a new tax year (each fall)

The IRS usually publishes next year's numbers between May and November:

| Usually published | What | Where |
| --- | --- | --- |
| May | HSA limits | Revenue Procedure ("HSA inflation adjusted items") |
| October/November | Brackets, standard deduction, capital gains thresholds, student loan phase-out, and more | Revenue Procedure ("inflation adjusted items for [year]") |
| November | 401(k) and IRA limits | IRS Notice ("cost-of-living adjustments") |
| October/November | Social Security wage base | SSA announcement; then IRS Publication 15 for that year |
| Any time | Law changes (like the 2025 One, Big, Beautiful Bill Act) | IRS newsroom, updated form instructions |

Steps:

1. Copy the latest file, for example `2026.json` to `2027.json`, and set `tax_year` and
   `last_reviewed`.
2. Go section by section. Replace each number from the new primary source and update the `sources`
   list and each section's `source_ids`. Some numbers are fixed in the law and don't change every
   year (for example, the $3,000 capital loss limit, the 3.8% investment income tax thresholds, and
   the $250 written-acknowledgment rule). Still confirm them, and say so in the `note`.
3. Watch for new laws. If a rule was added, changed, or expired, update the `note`. If a new kind of
   figure is needed, add it to the schema in `server/app/tax_data/__init__.py` and to every year's file.
4. If you can't confirm a number from a primary source, set it to `null` and explain in the `note`.
5. Add spot checks for a few key figures in `server/tests/test_tax_data.py` and update the list of
   years there. Run `ruff check .`, `ruff format --check .`, and `pytest` in `server/`.
6. Ask the `finance-tax-expert` agent to review the PR.

Also re-check the current year's file when the IRS publishes final forms and instructions in
December and January. Early numbers sometimes get corrected (for example, the IRS corrected the SALT
amount printed in the 2026 Form 1040-ES).

## Known gaps

- `senior_deduction.phaseout_rate` is `null`: the IRS pages we checked say where the phase-out starts
  but not how fast it reduces the deduction.
- Not covered yet: tax credits, the alternative minimum tax, state taxes, the new tips, overtime,
  and car loan interest deductions, and the 2026 limit on the tax benefit of itemized deductions for
  people in the 37% bracket. Add them when a feature needs them.
