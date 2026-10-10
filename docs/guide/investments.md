# Your investments and retirement savings

> **Estimates, not tax advice.** Values use live prices (if you turn them on) or prices you type in, and
> contribution limits come from IRS numbers Budget Buddy keeps for each year. Check with your broker, your plan, or a tax professional.

The **Investments** page (click **Money** at the top, then the **Investments** tab) shows what you own in each
account and how much you've put into retirement accounts and an HSA this year.

## What you hold, by account

Budget Buddy works this out from the purchases and sales you entered on the **Stocks** page (under **Taxes**).
For each account it lists every stock or fund you still hold:

- **Shares** still held, and what they **cost** you (including fees).
- **Price**: the latest price, *live* with the time it was fetched, or *typed in* with its date.
- **Value** at that price, and the **gain or loss** you'd have if you sold now. Nothing is taxed until you sell.
  Selling inside a retirement account or HSA isn't taxed; money you take out later may be, depending on the
  account.

Shares in a retirement account or HSA are listed too, marked *Not taxed when you sell inside this account*.

### Link stocks to an account

When you add a purchase or sale on the **Stocks** page, pick the **Account** it's in: a brokerage account, an IRA
or 401(k) (account type **Retirement**), or an **HSA**. Add the account first on the **Accounts** page if it isn't
there. Sales inside a retirement account or HSA aren't counted in your taxable gains, but buying a stock there can
still make a loss you took elsewhere a possible wash sale, so enter those purchases too. In that case the loss
isn't just postponed: it's lost for good.

### Live prices (optional)

Budget Buddy can get the latest prices for you from **Finnhub**, a stock price service. It's off until you turn
it on:

1. Sign up for a free account at finnhub.io and copy your **API key** from your Finnhub dashboard.
2. On the Investments page of the Budget Buddy computer, in the [All tools](open-the-dashboard.md#simple-view-or-all-tools) view, under **Live prices**, choose **On**, paste the key and
   click **Save**. (A connected computer can refresh prices but can't turn them on or change the key.)

From then on, prices refresh when you open the Investments page and when you click **Refresh prices**, never in
the background. Each price says **live** and the time it was fetched.

What's shared: only the symbols you hold (like VTI) are sent to Finnhub, one at a time. Never amounts, accounts or
anything else. Finnhub does see which symbols you look up, tied to your Finnhub account. Your key is stored
encrypted on this computer. To stop, choose **Off**, or click **Remove my key and turn off**.

If a price can't be fetched, the page says why (no internet, the key isn't accepted, or Finnhub's free limit of
60 a minute was reached) and keeps the last prices. Some mutual funds have no price on Finnhub: type those in.

### Type a price

Under **Type a price**, type the symbol, the price of **one share** (from your broker's website or app) and the
date, then click **Save price**. The new price replaces the old one, including a live one, and is marked
*typed in*.

## Stock trades from your bank file

Some brokers' files (Chase / J.P. Morgan, for example) show a stock purchase only as the company's name and a lot
of fine print, like `ABBOTT LABORATORIES UNSOLICITED WE ARE ACTING AS PRINCIPAL ...`, with a **deposit sweep** next
to it for the same amount (`CHASE DEPOSIT SWEEP ... INTRA-DAY WITHDRWAL`). The sweep is just the cash moving to pay
for the shares.

Budget Buddy finds these when you import the file, links each trade with its sweep, and lists them on the
**Investments** page under **Stock trades from your bank file**: the date, the company, **Bought** or **Sold**, and
the amount. Neither the trade nor the sweep counts as spending or income, and neither needs a category.

1. For each trade, type the **ticker** (like `ABT`) and the **number of shares** from your broker's trade
   confirmation, then click **Save**.
2. The row then shows the **price per share (with fees)**: the amount divided by the shares. The amount already
   includes any commission, so it's what each share cost you (or brought in after fees), which is what counts for
   taxes; it can differ a little from the trade price on your confirmation. The shares appear under the account
   above and on the **Stocks** page with the date you bought or sold.
3. Next time that company shows up, its ticker is already filled in: just add the shares.

Some brokers sweep a day's cash in one line, like two purchases paid by one sweep for their total. Budget Buddy
links that sweep to all of them when the amounts add up exactly.

A trade you marked yourself on the **Transactions** page (**Stock trade**) gets its sweep linked the same way, as
soon as the sweep is there, and then shows up in this list too.

Imported this file before this existed, or marked trades yourself before this? Click **Find trades in my
transactions**. If a line isn't really a trade,
click **Not a trade**: it then counts like any other transaction. Once you've recorded the shares, delete the
purchase or sale on the **Stocks** page instead. Cancelled or corrected trades, money market
funds and bonds coming due aren't counted as trades. Dividends and their sweeps are handled the same
way, on the Stocks page ([dividends](dividends.md)).

## Import your broker's positions file

Most brokers let you download your positions (also called holdings) as a CSV file. On the **Investments** page
(in the [All tools](open-the-dashboard.md#simple-view-or-all-tools) view), under **Import a positions file**, pick the account, the day the file is from, and the file, then click
**Preview** and **Save**.

- Budget Buddy shows what the file says you hold (**Broker says**) next to what your recorded purchases and sales
  add up to on the file's day (**Your records**), both ways: a stock you still hold by your records that the
  file doesn't list shows as **Not in the file** (a sale may be missing). Fewer shares than the broker means a
  purchase may be missing; more means a sale may be.
- If trades from your bank file in that account still need their shares, it says how many: that's usually why
  the shares differ. The check updates as soon as you add a trade or import a newer file.
- On the **Stocks** page, each purchase and sale says what backs it up (**Checked by**): **A transaction** (linked
  to a line in your bank or brokerage file), **Broker's positions file** (the newest file for that account agrees,
  and is dated on or after the trade), or **Not verified yet**. Set **Show** to **Not verified yet** to see only
  the ones to check.
- Prices in the file become your latest prices (shown as "from your broker's file"), unless you already have a
  price from a later day.
- It never changes your purchases, sales or gains. Saving a newer file for the same account replaces the old one;
  **Forget this file** removes it.
- Cash lines (like a money market fund marked `**`), short positions and notes at the bottom are skipped.

## Retirement and HSA contributions

This part shows, for the year you pick, how much you've put in and how much room is left:

| Line | What's counted | Limit |
| --- | --- | --- |
| 401(k) or 403(b) | Your own contributions on your pay stubs, traditional and Roth together | $24,500 in 2026 |
| IRA | The **IRA contribution** deductions you entered on the Tax summary page, plus money put into accounts marked **Roth IRA** | $7,500 in 2026 |
| HSA | Pay-stub HSA amounts plus **HSA contribution** deductions | $4,400 for just you, $8,750 for a family (shared by spouses), in 2026 |

- **Age catch-up:** at 50 or older you can put in more (and more again from 60 to 63 for a 401(k); at 55 or older
  for an HSA). Budget Buddy doesn't know your age, so it shows the extra amount without adding it.
- **A 457(b) plan** (common for government jobs) has its own separate limit, so leave its amounts out of the
  401(k) line.
- **Each person has their own 401(k) and IRA limit.** The totals add up every pay stub and deduction you entered,
  so if you entered a spouse's too, compare each person separately.
- **HSA:** don't also enter pay-stub HSA amounts as an HSA deduction (that counts them twice). If you weren't
  covered all year, your limit may be lower.
- **Roth IRA:** mark the account as **Roth IRA** on the Accounts page. Transfers into it, and deposits there that
  say "contribution", then count toward the IRA limit. Rollovers, conversions, moves from another IRA, 401(k) or
  HSA, dividends and sales don't. A contribution made early in the year for the year before is counted in the year
  it was made: check those. A refund of an excess contribution isn't taken off. Higher incomes can lower or remove
  what you're allowed to put in a Roth IRA.
- **Not included:** employer matches (they don't count toward your own 401(k) limit), and money your employer
  puts in your HSA if it isn't on your pay stub (it does count toward the HSA limit).
- If you're over a limit, the line says how much, in red unless an age catch-up could cover it. Talk to your plan
  or a tax professional about fixing an excess contribution.

## Something went wrong?

| What you see | What to do |
| --- | --- |
| "no price yet" | Turn on live prices, or add a price under **Type a price**. |
| "Finnhub didn't accept your key." | Copy the key from your Finnhub dashboard again and save it. |
| "Finnhub's free limit was reached." | Wait a minute and click **Refresh prices**. |
| "Couldn't reach Finnhub." | Check your internet connection. The last prices are kept. |
| "No price found for ..." | Finnhub doesn't have that symbol (often a mutual fund). Type its price in. |
| "Enter the price of one share, like 245.10." | Type the price in dollars and cents. |
| A holding is missing | It's only shown while you still hold shares. Check the purchases and sales on the Stocks page. |
| "Budget Buddy doesn't have tax rules for [year] yet." | Contribution limits only work for years with a tax data file. |
