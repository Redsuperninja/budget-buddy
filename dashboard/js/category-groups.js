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

// Needs and wants categories that went over their budget this month (monthly summary rows), most over first:
// [{ category_id, name, over_cents, over_percent }]. over_percent is how far past the budget, rounded down.
// skipPercent: leave out percentage budgets, for a month still going whose budgets follow the income received so far
// (a share of half a month's pay isn't the month's budget yet).
export function overBudget(categories, { skipPercent = false } = {}) {
  return categories
    .filter((c) => (c.group === "needs" || c.group === "wants") && c.budget_cents > 0 && c.actual_cents > c.budget_cents)
    .filter((c) => !(skipPercent && c.budget_percent_bp !== null))
    .map((c) => ({
      category_id: c.category_id, name: c.name, over_cents: c.actual_cents - c.budget_cents,
      over_percent: Math.floor(((c.actual_cents - c.budget_cents) * 100) / c.budget_cents),
    }))
    .sort((a, b) => b.over_cents - a.over_cents || a.name.localeCompare(b.name));
}

// The badge for how far over: "+17%", or "<1%" when it rounds down to nothing.
export const overBadge = (percent) => (percent > 0 ? `+${percent}%` : "<1%");
