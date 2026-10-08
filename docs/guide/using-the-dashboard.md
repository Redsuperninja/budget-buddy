# Using the Budget Buddy dashboard

The dashboard is a website that runs on your computer. It shows your budget, accounts, and spending.

## Open the dashboard

1. Start Budget Buddy on your computer (the Home Base).
2. Open a web browser (Chrome, Edge, Firefox, Safari — any browser works).
3. Go to <http://127.0.0.1:8765/> or type that address in the address bar.
4. You'll see the Budget Buddy dashboard with a row of buttons at the top: Home, Accounts, Transactions, Categories, and more.

**Your data stays on this computer.** The dashboard only works when you open it here. You can't access it from other computers or your phone.

## Home

Shows your budget for the current month: money in, money spent, money saved, and account balances.

- **Month:** Click the month box to pick a different month.
- **Categories:** See how much you budgeted vs. actually spent in each category (Needs, Wants, Savings, Income).
- **Unassigned transactions:** If you see a note about transactions with no category, go to **Transactions** to assign categories.

## Accounts

Lists all your bank and savings accounts, and their current balances.

**Add an account:**

1. Scroll down to "Add an account".
2. Enter the account name (e.g., "Everyday checking").
3. Pick the type: Checking, Savings, Credit card, or other.
4. Bank name is optional.
5. Click **Add account**.

**Record a starting balance:** Go to **Transactions**, add a transaction with type "Balance adjustment" for the amount. This doesn't count as income or spending.

## Transactions

Lists all the money coming in and going out, and lets you add more.

**Filter and view:**

- **Account:** Click to see transactions from one account only.
- **Month:** Click to see transactions from one month only.

**Add a transaction:**

1. Scroll down to "Add a transaction".
2. Pick the account.
3. Pick the date.
4. Pick "Money out (spent)" or "Money in (received)".
5. Enter the amount in dollars (e.g., 12.50).
6. What was it? (e.g., "Gas", "Paycheck"). Required.
7. Pick a category (optional — leave it blank for now and come back later).
8. Type: "Regular", "Refund", or "Balance adjustment" (usually Regular).
9. Click **Add transaction**.

**Assign a category later:**

1. Find the transaction in the list.
2. Click the "Category" dropdown and pick one.
3. It saves automatically — you'll see "Saved".

## Categories

Lists all your budget categories and their monthly budgets.

**Set a budget:**

1. Find the category in the list (or add a new one first).
2. Enter the monthly budget amount in dollars (e.g., 250.00).
3. Click **Save**.
4. The same budget applies to every month.

**Add a category:**

1. Scroll down to "Add a category".
2. Enter the category name (e.g., "Groceries").
3. Pick a group: Needs (food, utilities, rent), Wants (entertainment, dining out), Savings (emergency fund, investments), or Income.
4. Enter a monthly budget (or leave it at 0).
5. Click **Add category**.

## Import bank file

Download a CSV file from your bank's website and import it into Budget Buddy.

**Before you start:**

- You need at least one account set up (go to **Accounts** first).
- Download a CSV file from your bank. (On your bank's website, look for "Download", "Export", or "Statements" — pick CSV format.)

**Import the file:**

1. Pick the account to import into.
2. Click "CSV file" and choose the file you downloaded.
3. Click **Preview**.
4. Budget Buddy shows the rows it found. Check that dates and amounts look right.
5. If something's wrong (wrong columns, backwards signs), adjust the settings and click **Update preview**.
6. Click **Import [number] new row(s)**.

**Tips:**

- Importing the same file twice is safe: rows already there are skipped.
- Credit card statements often show charges as positive numbers. If that's wrong, set "Charges show as positive numbers?" to "Yes, flip them".
- The first time you import from a bank account, Budget Buddy asks which column is which. Next time it remembers your choice.

## Connect phone

Pair your phone so it can sync budget updates.

**Pair a phone:**

1. Make sure both your phone and computer are on the same home Wi-Fi (not a guest network).
2. Click **Show pairing code**.
3. Budget Buddy shows a QR code that works for 10 minutes and counts down.
4. On your phone, open Budget Buddy, go to Settings, then Connect, and scan the QR code.
5. If the camera can't scan, click **Show code as text** and paste the text into your phone instead.
6. When the phone pairs, you'll see "New phone paired".

**See connected phones:**

1. Scroll down to "Connected phones".
2. You'll see each phone's name, when it was paired, and when it last synced.

**Remove a phone:**

1. Find the phone in the list.
2. Click **Remove**.
3. The phone stops working right away. You can pair it again later if you want to.

## Paychecks

Track your pay stubs and tax withholding. (Estimate only, not tax advice.)

**Add a paycheck:**

1. Click **Paychecks**.
2. Scroll down to "Add a paycheck".
3. Enter the pay date, employer, and the numbers from your pay stub (gross pay, federal tax, state tax, Social Security, Medicare, 401k contributions, HSA, health insurance, Roth 401k, other deductions, and net/take-home pay).
4. If you're not sure about some amounts, leave them blank or enter 0.
5. Click **Add paycheck**.

**View by year:** Pick a year at the top to see paychecks from a different year.

## Donations

Track charitable gifts for tax time. (Estimate only, not tax advice.)

**Add a donation:**

1. Click **Donations**.
2. Scroll down to "Add a donation".
3. Enter the date, charity name, type (cash/check/card or goods), and amount.
4. Click **Add donation**.

**View by year:** Pick a year at the top to see donations from a different year.

## Stocks

Track stock purchases and sales to calculate gains and losses. (Estimate only, not tax advice.)

**Add a purchase:**

1. Click **Stocks**.
2. Scroll down to "Add a purchase".
3. Enter the symbol (e.g., "VTI"), the date you bought it, number of shares, and total cost (including fees).
4. Click **Add purchase**.

**Add a sale:**

1. Scroll down to "Add a sale".
2. Enter the symbol, date sold, number of shares, and total received (after fees).
3. Click **Add sale**.

Budget Buddy calculates gains and losses and flags possible wash sales.

## Something went wrong?

**"This page only works on this computer."**

The dashboard only works when you open it from this computer. You can't use it from your phone, another computer, or over the internet. Open <http://127.0.0.1:8765/> in a browser on the same computer where Budget Buddy is running.

**The page won't load.**

1. Make sure Budget Buddy (the Home Base) is running.
2. Try typing the address again: <http://127.0.0.1:8765/>
3. If it still doesn't work, close your browser and try a different one.
4. Restart Budget Buddy.

**Numbers don't look right.**

- Check that transactions have the right category.
- Go to **Home** and look for the note about "unassigned" transactions — assign them a category.

**I can't connect my phone.**

- Both your phone and computer must be on the same home Wi-Fi (not a guest network).
- Budget Buddy must be running on your computer.
- The pairing code only works for 10 minutes — if it runs out, click **Show pairing code** again.
