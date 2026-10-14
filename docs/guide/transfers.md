# Transfers between your accounts

When you move money between your own accounts (paying your credit card, putting money into savings, adding to
your IRA or 401(k), or taking money back out), the same amount leaves one account and arrives in another. That
isn't spending or income, so Budget Buddy links the two sides as one **transfer** and leaves them out of your
spending and income.

## Budget Buddy finds them for you

When you import a bank file or add a transaction, Budget Buddy looks for the other side: the **same amount**
going out of one of your accounts and coming into another, **within 5 days** (transfers and card payments can
take a few days to show up on the other side). At least one side has to say it's a transfer or payment, with
words like "transfer", "payment", "autopay", "thank you" or "ACH", because the same amount alone is often a
coincidence. When there's exactly one clear match, it links them.

On the **Transactions** page, a linked transfer shows what kind it is next to its category:

| Shown as | Example |
| --- | --- |
| Credit card payment | Checking to your credit card |
| Loan payment | Checking to a car loan or mortgage |
| Into savings / investments / retirement / HSA | Checking to savings, a brokerage account, an IRA or 401(k), or an HSA |
| Out of savings / investments / retirement / HSA | Money moved back to checking |
| Between accounts | Anything else, like checking to cash |

Money moved **into** savings, investments, retirement or an HSA counts as **saved** on the Home page; moving it
back out lowers what you saved. A credit card payment doesn't count as spending, because the purchases on the card
already did.

**Credit card payments** go in the **Payments** category, on both sides: the payment out of your checking account
and the payment into the card. Budget Buddy files them there even before both sides are linked, when the line says
it's a payment (like "AUTOPAY" or "THANK YOU") and, on the checking side, names a credit card (like "CREDIT CARD
PAYMENT", "AMEX" or "DISCOVER") and the card you added (a word of its name or bank, like "Chase" for a card you
called "Chase Freedom"). Debit-card purchases, loan payments and moves to a savings account at a card
company's bank (like Discover Bank or Capital One 360) are never filed there. A payment that was returned goes in **Payments** too, since it cancels the payment.

A payment to a card you haven't added to Budget Buddy isn't filed this way, since it's the only record of what you
spent on that card: add the card too, or give that payment a category yourself so it counts. A category you picked
yourself is never changed, and a line you take out of **Payments** (by clearing its category) stays out. If you already
have a category called Payments for something else, card payments stay in **Transfer** instead.

Both sides need to be in Budget Buddy, so add both accounts and import (or enter) both sides.

- **Loan payments:** if your lender's file shows the whole payment, the interest part is linked too, so it isn't
  counted as spending. To count the interest, undo the link and give the payment a category.
- **Money out of retirement or an HSA** may have tax rules (taxes, penalties, or medical receipts to keep).
  Budget Buddy only tracks the move. Estimate only, not tax advice.

## When it doesn't link them

Budget Buddy leaves a pair for you when it can't be sure:

- the amounts differ, even by a cent, or the dates are more than 5 days apart;
- neither description says it's a transfer or payment, or the credit card side doesn't look like a payment (a
  refund or credit on the card isn't a payment);
- one side looks like a dividend, interest, an employer match, pay, a refund or cash back;
- two possible matches are equally close;
- one side already has a category (from you or an auto-sort rule) other than Transfer;
- one side is the deposit linked to a paycheck, or a donation;
- the money leaves a credit card or loan (a cash advance, balance transfer or loan payout): link those yourself;
- you unlinked them before.

Click **Find transfers** on the Transactions page (in the [All tools](open-the-dashboard.md#simple-view-or-all-tools) view) to look through everything again, for example after adding an
account. To link a pair by hand, or undo a link, use the transfer options on the transaction. Undoing a link puts
back the category each side had before (so it counts as spending or income again), and Budget Buddy never links
those two automatically again.

## Something went wrong?

| What you see | What to do |
| --- | --- |
| Two unrelated transactions were linked | Undo the link. Each side gets its old category back, and the link won't be made again. |
| A card payment shows as spending | Add the credit card as an account and import its statement, so both sides are there. Then click **Find transfers**. Older card payments move to **Payments** when you click **Match everything again** on the Transactions page. |
| A purchase or loan payment landed in **Payments** | Pick its category yourself on the **Transactions** page, or clear it; either way it stays. (Auto-sort rules only sort lines with no category, so they won't move it.) |
| "No new transfers found." | Nothing new matched. Check that both sides are in Budget Buddy with the same amount, a few days apart at most. |
