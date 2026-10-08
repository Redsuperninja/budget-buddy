# What to test

## What's ready to try

| Part | What works | Not built yet |
| --- | --- | --- |
| Computer dashboard | Accounts, transactions, categories, budgets, monthly summary, bank CSV import, paychecks, donations, receipts, stocks, connecting your phone | Editing or deleting most items (you can add and view; ask if you need to fix something) |
| Phone app | Connecting to your computer, Home and Taxes screens | Showing your real data (it shows sample data until sync), receipt photos, the Sync button and reminders |

## Checklist

Open http://127.0.0.1:8766/ on your computer and use the buttons along the top (Home, Money, Budget, Taxes, Phone) and the tabs under them.

- [ ] **Monthly summary:** on **Home**, pick this month. Do income and spending look right? Is the "not sorted yet" money clear?
- [ ] **Categories:** add one, rename it, give it a budget. Try a name that already exists. Type `15%` as a budget, and set a planned monthly income.
- [ ] **Suggested budget:** does the plan make sense for the demo data? Try "Use as percentages of income".
- [ ] **Auto-sort:** add a rule (for example `GROCERY` to Groceries), then import a bank file or click "Sort transactions now".
- [ ] **Transactions:** add a purchase (choose "Money out", amount `12.34`). Add a refund.
- [ ] **CSV import:** on **Import bank file**, choose `scripts\sample-bank-statement.csv`, check the preview, then import. Do it again: rows already there should be skipped.
- [ ] **Paychecks:** add one whose numbers don't add up. Is the message clear?
- [ ] **Donations:** look at the year summary for this year. Does the "proof to keep" list make sense?
- [ ] **Stocks:** look at the gains for this year. Add a sale of more shares than you own.
- [ ] **Tax summary:** add a medical deduction, download the CSV and open it in a spreadsheet, then try "Print or save as PDF".
- [ ] **Phone:** connect, then disconnect and connect again. Try scanning an old or used code.
- [ ] **Messages:** were any error messages confusing or too technical? Note the exact words.

## How to report what you find

Open an issue on GitHub with the "User testing feedback" template, or write down:

1. What you were trying to do
2. What you expected to happen
3. What happened instead (the exact message, or a screenshot)

**Please don't include real financial information in reports.**

## Something went wrong?

**"The test Home Base isn't running"**

Start window 1 from [Start a test session](start-a-test-session.md) and leave it open.

**"Budget Buddy isn't set up on this computer yet"**

Run the setup script from [Set up for testing](set-up-for-testing.md).

**The page won't load**

1. Make sure the test Home Base is running (window 1)
2. Try typing the address again: http://127.0.0.1:8766/
3. If it still doesn't work, close your browser and try a different one
4. Restart the test Home Base

**When you finish a session**

Press Ctrl+C in each window. That stops the phone app's test server too, which otherwise stays reachable on your home Wi-Fi.
