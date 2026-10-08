# Stocks: purchases, sales, and gains

> **Estimates, not tax advice.** Budget Buddy helps you keep track and gives you a rough idea of
> your gains and losses. Before you file, check everything against the Form 1099-B from your
> broker, your tax software, or a tax professional.

Budget Buddy can keep a record of stocks and funds you buy and sell in a regular (taxable)
brokerage account. It works out how much you gained or lost on each sale, whether that counts as
short term or long term, and adds it all up for each tax year. Enter your purchases and sales in the Budget Buddy dashboard on your computer.

## Entering a purchase

For each time you bought shares, enter:

- **Symbol**, like `VTI` or `BRK.B`. Upper or lower case is fine.
- **Date you bought them.**
- **Number of shares.** Fractions are fine, up to 6 decimal places (for example `2.5`).
- **Total you paid, including any fees.** For example, if 10 shares cost $1,000.00 plus a $5.00
  fee, enter `1005.00`.
- **Account** (optional): the brokerage account they're in.

If you bought the same stock several times, enter each purchase separately. Each one is called a
"lot".

## Entering a sale

For each time you sold shares, enter:

- **Symbol** and **date you sold them.**
- **Number of shares sold.**
- **Total you received after fees.** For example, if you sold for $1,500.00 and paid a $5.00 fee,
  enter `1495.00`.
- **Account**: the same account as the purchases. Shares in another account aren't used.

Budget Buddy sells your **oldest shares first** (this is called "first in, first out", or FIFO, and
it's what the IRS assumes unless you told your broker otherwise). One sale can use shares from
several purchases, and can use just part of a purchase. The sale shows which purchases it used.

If you forgot a purchase and enter it later, that's fine: Budget Buddy matches your sales again so
the oldest shares are still sold first.

## Short term or long term?

- **Short term**: you held the shares **one year or less**.
- **Long term**: you held them **more than one year**. Long-term gains are usually taxed at a lower
  rate.

The clock starts the day **after** you bought. For example, shares bought on March 10, 2025 are
long term if sold on March 11, 2026 or later. Sold on March 10, 2026, they're still short term.
Leap years are handled: shares bought on February 29, 2024 become long term on March 1, 2025.
Each purchase shows the first date its shares count as long term.

## Your yearly summary

For each tax year you see:

- **Short-term total** and **long-term total**: what you received, what the shares cost you, and
  the gain (a negative number is a loss).
- **Total gain or loss** for the year.
- How many sales are flagged as a **possible wash sale**.

A sale counts in the year of its sale date.

## What "possible wash sale" means

If you sell at a **loss** and buy the same stock within **30 days before or after** that sale, the
IRS may not let you deduct that loss this year. Instead, it's added to the cost of the shares you
bought. This is called a wash sale.

Budget Buddy only **flags** a possible wash sale. It doesn't change any numbers. If you see the
flag, check your broker's Form 1099-B or ask a tax professional.

We only compare purchases of the same symbol entered here. Buying the same stock in an IRA or HSA,
or a spouse buying it, within 30 days of a sale at a loss can also cause a wash sale. We don't
check those purchases.

## Something went wrong?

- **"You're selling more shares of ... than you owned"**: check the number of shares and the
  date. Only purchases in the same account, dated on or before the sale, count. If a purchase is
  missing, add it first, then enter the sale again.
- **"This sale would leave your later sale ... selling more shares than you owned"**: the sale
  you're adding is dated before another sale and would use shares that later sale needs. Check the
  dates and numbers, or add the missing purchase.
- **"Your sale of ... needs the shares from this purchase"**: you can't delete a purchase a sale
  still uses. Delete that sale first.
- **A mistake in a purchase or sale**: there's no editing yet. Delete it and enter it again. Your
  other sales are matched again automatically.
- **"Sales inside a retirement account or HSA aren't taxed"**: those accounts can't be used here.
  Pick a regular brokerage account, or leave the account empty.
- **An account can't be deleted, or changed to a retirement account or HSA**: it still has stock
  purchases or sales. Delete those first, or add a separate account.
- **The numbers don't match your broker**: your broker may use a different method than "oldest
  first", or may have adjusted a wash sale. Your Form 1099-B is the official record.
