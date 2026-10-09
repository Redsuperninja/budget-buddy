# Import stocks from a CSV file

Instead of typing in each purchase and sale, you can add them all at once from a spreadsheet or a file
downloaded from your broker. Budget Buddy shows you what it found before anything is saved.

## 1. Get the file ready

The file needs to be a CSV file (in Excel or Google Sheets: **Save as** or **Download**, then pick CSV). Its
first row has to name the columns. Budget Buddy looks for:

| Column | Other names that work | What goes in it |
| --- | --- | --- |
| **Symbol** | Ticker | Like `VTI` or `BRK.B` |
| **Date** | Trade date, Date acquired, Date sold | The day you bought or sold |
| **Shares** | Quantity, Qty | How many shares, like `10` or `2.5` |
| **Cost** | Amount, Cost basis, Proceeds, Total | The **total** paid including fees, or received after fees, not the price per share |
| **Type** (optional) | Action | **Buy** or **Sell** |

Without a **Type** column, every row is added as a purchase. Other columns (like Price or Description) are
ignored, so a broker's own file often works as it is. A minus sign on shares or money is fine.

A small example:

```
Type,Symbol,Date,Shares,Cost
Buy,VTI,2025-01-10,5,1005.00
Sell,VTI,2026-03-01,2,560.00
```

## 2. Import it

1. In the dashboard, go to **Taxes**, then **Stocks**, and scroll to **Import from a CSV file**.
2. Pick the **Account** the shares are in (or leave it as "(none)"), and choose your file.
3. Click **Preview**. You'll see how many purchases and sales are new, which are already in Budget Buddy, and any
   rows with a problem, with the reason.
4. Click **Import**. If some rows have a problem, either fix them in the file and preview again, or choose
   **Yes, skip those rows**.

Importing the same file twice is safe: rows already added are skipped. Sales use your oldest shares first, the
same as sales you type in (see [Stocks](stocks.md)).

## Something went wrong?

- **"We couldn't find the columns"**: the first row of the file needs column names like Symbol, Date, Shares
  and Cost. Add a row at the top with those names.
- **"The type should say Buy or Sell"**: that row is something else, like a dividend. Delete the row, or choose
  to skip rows with problems.
- **"The sale of ... is for more shares than you owned then"**: the file sells shares Budget Buddy doesn't know
  you had in that account by that date. Add the missing purchases to the file (or enter them first), then
  import again. Nothing was saved.
- **Wrong numbers**: check the Cost column is the total for the row, not the price of one share.
