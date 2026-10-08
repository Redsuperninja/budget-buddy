# Auto-categorization rules

Code: `services/category_rules.py`, `services/category_learning.py`, `routers/category_rules.py`, table
`category_rules` (migrations 0009, 0014). Roadmap items 9 and 9b.

## Routes (this computer only)

- `GET/POST /api/local/category-rules`, `GET/PATCH/DELETE /api/local/category-rules/{id}`.
  A rule is `{pattern, category_id}`. The pattern is 2 to 100 characters, unique ignoring upper/lower case
  (`409 pattern_taken`).
- `POST /api/local/category-rules/apply`: sort every `normal` transaction that has no category yet.
  Returns `{"categorized": N}`.

## Matching

- A rule matches when its pattern appears anywhere in the description, ignoring upper/lower case (`casefold`).
- **Longest pattern wins** (the most specific). Same length: the older rule (lower id) wins. There is no
  manual ordering to keep in sync.
- Deleting a category deletes its rules (`ON DELETE CASCADE`).

## When rules run

- **Bank CSV import:** each new row gets the winning rule's category. The import result has `categorized`.
- **Manual entry:** only when `category_id` is left out of the request and the kind is `normal`. Sending
  `"category_id": null` means "no category on purpose" and is left alone.
- **On request:** `POST .../apply`, for transactions imported before a rule existed.

Rules **never** change a category already set, and never touch transfers, refunds or adjustments: those
follow the rules in [ledger.md](ledger.md). A rule may point at the Transfer category (for example for bank
moves you don't link as a transfer); the monthly summary then ignores those rows, as for any normal
transaction in that category ([budget-summary.md](budget-summary.md)).

## How a category was set

`transactions.category_source` is `"rule"` (with `sorted_by_rule_id`) when a rule set it (import, manual entry,
`apply`, or right after a rule is learned) and `"you"` when someone picked it (a PATCH or POST that sends
`category_id`, or marking a gift); `None` for older rows and for Budget Buddy's own choices (transfers).
`sorted_by_rule_id` has no foreign key (migration 0014 only adds columns, since rebuilding `transactions` would
fire other tables' `ON DELETE` rules); deleting a rule clears it in code, while a category delete that cascades to
its rules leaves the old ID behind (shown as "a removed rule").

- `GET /api/local/transactions?sorted_by=rule|you` lists them.
- `GET /api/local/category-rules` adds `learned` and `sorted_count` (transactions still carrying that rule's
  sorting).

## Learning (`services/category_learning.py`)

After a category is picked by hand, `shop_key` takes the start of the description (up to three words, skipping
generic bank words like POS or DEBIT, stopping at a word with a digit; at least 3 letters). When 3 hand-picked
regular transactions starting with that key share a category, and none starting with it were picked into another
one, a rule `{pattern: key, learned: true}` is added and `apply` runs. Nothing is learned when a rule with that
text exists or an existing rule at least as long already matches (yours are never outranked). The PATCH or POST
reply carries `learned_rule` (the new rule's text) once.

Patterns and descriptions are never logged.
