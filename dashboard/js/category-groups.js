import { formatCents } from "./money.js";
import { formatBp } from "./percent.js";

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

// What's left of a month's budget for a category: { state: "left" | "over" | "none", cents }. Refunds bigger than
// the spending leave the whole budget; with no budget, cents is what was spent.
export function budgetLeft(actual, budget) {
  const spent = Math.max(0, actual);
  if (budget <= 0) return { state: "none", cents: spent };
  return spent > budget ? { state: "over", cents: spent - budget } : { state: "left", cents: budget - spent };
}

// The words around a budget's meter or ring: { right, below, alarm, used }.
// row: { actual, budget, saving?, percent_bp? } in cents. saving reads as a goal ("to go", "extra", never alarming,
// and money taken out says so). provisional: the month is still going and percentage budgets follow the pay received
// so far, so a percentage budget is only "so far" and never alarming (percent_bp marks one).
// used: the share to draw (0 or more), rounded down when shown as a percentage elsewhere.
export function budgetWords(row, { provisional = false } = {}) {
  const { actual, budget, saving = false, percent_bp: bp = null } = row;
  const soFar = provisional && bp !== null;
  const tail = soFar ? " so far" : "";
  const used = budget > 0 ? Math.max(0, actual) / budget : 0;
  const did = saving ? "saved" : "spent";
  const below = saving && actual < 0 ? `${formatCents(-actual)} taken out`
    : `${formatCents(Math.max(0, actual))} ${did}${budget > 0 ? ` of ${formatCents(budget)}${tail}` : ""}`;
  if (budget <= 0) {
    return { right: soFar ? `${formatBp(bp)} of income` : "No budget", below, alarm: false, used };
  }
  const left = budgetLeft(actual, budget);
  const words = saving ? { left: "to go", over: "extra" } : { left: "left", over: "over" };
  return { right: `${formatCents(left.cents)} ${words[left.state]}${tail}`, below,
    alarm: left.state === "over" && !saving && !soFar, used: saving ? Math.min(1, used) : used };
}
