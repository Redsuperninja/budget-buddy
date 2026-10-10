# Import your brokerage activity

Your broker's activity (or "history") file lists everything that happened in an account: deposits, purchases,
sales, dividends, fees. Import it once and Budget Buddy sorts it for you, so there's nothing to classify by hand.

## Import it

1. On your broker's website, download the account's activity or history as a CSV file.
2. In Budget Buddy, go to **Money**, then **Import files**, and scroll to **Import brokerage activity**.
3. Pick the account (a brokerage, IRA, 401(k) or HSA account) and the file, and click **Preview**.
4. Check the rows. The **Stock trade** column shows the ones that will also be recorded as purchases or sales.
5. Click **Import**.

## What happens

- **Every row becomes a transaction** in that account, with the broker's wording.
- **Buys and sells** that list a symbol and number of shares are also recorded on the **Stocks** page, linked to
  their transaction, and sold oldest shares first. They aren't spending or income in your budget.
- **Dividends** go in the **Dividends** category, with their deposit sweeps (see [Dividends](dividends.md)).
- **Everything else** (deposits, fees, interest) is sorted by your auto-sort rules, and moves from your other
  accounts are matched as transfers.
- A trade already on the Stocks page (from a stock file, or typed in) is linked to its transaction, not added twice.
- Your money market fund (the account's cash, like a symbol ending in XX) isn't treated as a stock.
- Rows where no money moved (shares moved in from another broker, a split) are skipped.
- Importing the same file again, or one that overlaps, only adds what's new.
- The file is listed in **Import history**, where **Remove** undoes it.

## Something went wrong?

- **"We couldn't find the columns"**: the file needs column names for the date, the action and the amount.
- **Rows with no money moved** are skipped: add shares moved in from elsewhere on the Stocks page if a later sale
  needs them.
- **"The sale of ... is for more shares than this account held then"**: the file sells shares bought before it
  starts. Import the earlier activity file first, or add those purchases on the Stocks page. Nothing was imported.
- **Short sales, options and corrections** are imported as transactions only. Record them on the Stocks page by
  hand if you need them there.
