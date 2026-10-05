# Tracking your charitable donations

> **Estimates, not tax advice.** Budget Buddy helps you keep the right records for your gifts to
> charity. It doesn't decide what you can deduct. Tax rules have many exceptions. Before you file,
> check IRS Publication 526, your tax software, or a tax professional.

Budget Buddy keeps a list of the gifts you give to charities and, for each tax year, tells you
what proof to keep. Today you add gifts through the Home Base on your computer (the
`/api/local/donations` part of the app). A screen for this in the computer-side dashboard comes
later.

## Logging a gift

For each gift, enter:

- **Date:** the day you paid. That's the day you mailed a check or the day your card was charged,
  even if you pay the card off later. For goods, it's the day you dropped them off.
- **Charity:** the charity's name.
- **Kind:** **cash** for money (cash, check, card, or bank transfer), or **goods** for things
  you gave, like clothes or furniture.
- **Amount:** for cash, how much you gave. For goods, what the items were worth when you gave them
  (what they'd sell for in their condition, often much less than you paid). If you got something
  back, like a dinner at a fundraiser, enter only the part above what it was worth.
- **Receipt (optional):** link a receipt you've already saved in Budget Buddy.
- **Notes (optional):** anything you want to remember. Notes are stored encrypted.

A few rules:

- The amount must be more than zero. If a gift was refunded or returned, edit or delete it instead.
- You can't log a gift for a future date. A promise to give (a pledge) counts once you pay it. A
  date one day ahead is allowed, in case your phone is in a time zone ahead of your computer.
- A gift counts in the calendar year of its date. A check mailed on December 31 counts in that
  year.

## What proof to keep

The yearly summary lists what to keep for each gift. The dollar amounts below are the ones for
2025 and 2026. Budget Buddy reads them from each year's tax data file, so they'll update if the IRS
changes them.

| Your gift | What to keep |
| --- | --- |
| Cash under $250 | A bank or card statement, or a receipt from the charity, showing the charity's name, the date, and the amount |
| Goods under $250 | A receipt from the charity with its name, the date, and a description of what you gave, plus your own note of what the items were worth |
| Any single gift of $250 or more (cash or goods) | A written acknowledgment from the charity, which you need before you file. It must show how much you gave (or describe the items) and whether you got anything in return, and if so, about what it was worth. A bank record alone isn't enough. |
| Goods of $250 or more | The written acknowledgment, plus your own note of what the items were worth and how you figured it |
| One goods gift worth more than $5,000 | Usually a qualified appraisal and Section B of Form 8283, signed by the charity. Some gifts, like publicly traded stock, don't need one. |

Separate gifts are not added together for the $250 rule. Two $150 gifts each need only a bank
record or receipt.

Some paperwork depends on all your gifts of goods for the year:

- **More than $500 of goods in total:** if you itemize, you'll likely need to file Form 8283 with
  your return. For each item, keep a note of when and how you got it and what you paid for it.
  Exactly $500 doesn't need it.
- **More than $5,000 of goods in total, but no single gift over $5,000:** if several were similar
  items (like clothing or furniture), add their values together. If those add up to more than
  $5,000, you'll likely need a qualified appraisal and Section B of Form 8283.

## Your yearly summary

The summary for a tax year shows:

- how many gifts you gave, and your cash, goods, and overall totals
- the proof to keep for each gift, and whether you've linked a receipt to it
- the paperwork that depends on the whole year (see above)
- the dollar thresholds used and the date that year's tax data was last checked

**These totals are what you gave, not what you can deduct.** How much counts depends on whether you
itemize and on your income. Budget Buddy doesn't work out your deduction yet.

### New for 2026: if you don't itemize

Starting with tax year 2026, people who take the standard deduction can still deduct some cash
gifts. The 2026 summary includes this note: "If you don't itemize, only cash gifts count, up to
$1,000.00 ($2,000.00 if married filing jointly)." Gifts of goods don't count for this. The 2025
summary doesn't show the note because the rule doesn't exist for 2025.

## Something went wrong?

| What you see | What to do |
| --- | --- |
| "Enter a gift on the day you actually gave it. A pledge counts once you pay it." | The date is in the future. Use the day you paid. |
| "A donation amount must be more than zero..." | Enter the amount you gave. To undo a refunded gift, edit or delete it. |
| "The amount can't be zero." | Enter the amount you gave, more than zero. |
| "Send either amount_cents or amount, not both." | Enter the amount only once. |
| "That receipt doesn't exist. It may have been deleted." | Pick a receipt that's still saved, or leave the receipt empty. |
| "That donation doesn't exist. It may have been deleted." | The gift was already removed. Refresh your list. |
| "Budget Buddy doesn't have tax rules for [year] yet. Years it has: ..." | Summaries work only for years that have a tax data file. Your gifts are still saved, and the summary will work once that year is added. |
| A "not_this_computer" error | Donations can only be viewed and changed on the computer running the Home Base, not from another device. |
