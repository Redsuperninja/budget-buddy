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

1. Open the dashboard and click **Auto-sort** at the top.
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

## When more than one rule fits

The rule with the **longest** text wins, because it's the most specific. With rules for "AMAZON"
(Shopping) and "AMAZON PRIME" (Subscriptions), a description "AMAZON PRIME VIDEO" goes to Subscriptions.

## Remove a rule

Click **Remove** next to it. Transactions it already sorted keep their category. If you delete a category,
its rules go with it.

## Something went wrong?

- **"You already have a rule for that text."** Each text can only have one rule. Remove the old one first.
- **"That category doesn't exist."** It may have been deleted. Reload the page.
