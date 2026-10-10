# Sort transactions automatically

Typing a category for every coffee and grocery trip gets old. Auto-sort rules do it for you.

## What a rule is

A rule says: **"If the description contains this text, put it in this category."**

For example:

| Description contains | Category |
| --- | --- |
| GROCERY MART | Groceries |
| NETFLIX | Subscriptions |
| PAYROLL | Paycheck |

Upper and lower case don't matter, so "netflix" also matches "NETFLIX.COM 866-555".

## Add a rule

1. Open the dashboard and turn on the [All tools](open-the-dashboard.md#simple-view-or-all-tools) view (**Settings** at the top right, **View**, **All tools**). Click
   **Money** at the top, then the **Auto-sort** tab.
2. Under **Add a rule**, type the text to look for. Copy it from a transaction's description; a short,
   distinctive part works best (at least 2 characters).
3. Pick the category and click **Add rule**.

## When rules are used

- **Importing a bank file:** new rows are sorted as they come in. The message at the end says how many
  were sorted by your rules.
- **Adding a transaction by hand** without picking a category.
- **Sort transactions now:** click this on the Auto-sort page to sort older transactions that still have
  no category.

Rules never change a category you picked yourself. They also leave transfers, refunds and balance
adjustments alone.

## Budget Buddy learns from your choices

You don't have to write rules yourself. When you pick a category for a transaction, Budget Buddy notes it. After
you've put **three** transactions from the same shop in the same category (and never put that shop anywhere else),
it adds a rule for that shop and sorts the matching transactions that have no category yet. The row says
*Saved. From now on, "STARBUCKS STORE" is sorted here automatically.*

"The same shop" is the start of the description, up to three words, stopping at numbers like store numbers or
dates, and skipping bank words like "POS" or "DEBIT". So "STARBUCKS STORE 12345" and "STARBUCKS STORE 678" are the
same shop.

Learned rules show **Learned from your choices** on the Auto-sort page. They work like any other rule: remove one
if you don't want it. Budget Buddy never learns a rule that would override one you added yourself.

## See what was auto-sorted

- On the **Auto-sort** page, the **Sorted** column shows how many transactions each rule sorted, and **Auto-sorted
  transactions** lists the newest 100 with the rule that sorted each one.
- On the **Transactions** page, set **Show** to **Sorted automatically** (or **Sorted by you**) to see them by
  month. Auto-sorted rows say *auto-sorted* next to the category.
- If a rule got one wrong, just pick the right category. That counts as your choice from then on.

## When more than one rule fits

The rule with the **longest** text wins, because it's the most specific. With rules for "AMAZON"
(Shopping) and "AMAZON PRIME" (Subscriptions), a description "AMAZON PRIME VIDEO" goes to Subscriptions.

## Remove a rule

Click **Remove** next to it. Transactions it already sorted keep their category (they no longer show which rule
sorted them). If you delete a category, its rules go with it.

## Something went wrong?

- **"You already have a rule for that text."** Each text can only have one rule. Remove the old one first.
- **"That category doesn't exist."** It may have been deleted. Reload the page.
