# Auto-categorization rules

Code: `services/category_rules.py`, `routers/category_rules.py`, table `category_rules` (migration 0009).
Roadmap item 9.

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

Patterns and descriptions are never logged.
