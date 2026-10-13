// Categories sorted into their groups (needs, wants, savings, income, then transfer), each with how many it has and
// what its monthly budgets add up to: amounts and percentages kept apart, since a percentage depends on income.

const ORDER = ["needs", "wants", "savings", "income", "transfer"];

export function byGroup(categories) {
  return ORDER.map((group) => {
    const items = categories.filter((c) => c.group === group);
    return {
      group,
      categories: items,
      budget_cents: items.reduce((sum, c) => sum + (c.budget_percent_bp === null ? c.budget_cents : 0), 0),
      budget_percent_bp: items.reduce((sum, c) => sum + (c.budget_percent_bp || 0), 0),
    };
  }).filter((g) => g.categories.length);
}
