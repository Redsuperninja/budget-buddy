// The plain sentence above the Home "Spending pace" chart. pace: the server's SpendingPace; percentBudgets: whether
// any budget is a share of income (with no income yet, those budgets are $0).

import { projected } from "./charts/pace.js";
import { formatCents } from "./money.js";

const CLOSE = 0.05; // where the month is heading, within 5% of the budget, counts as on track
const EARLY_DAYS = 7; // before this, one big bill (rent) makes any projection look wild

function heading(spent, budget, day, days) {
  const end = projected(spent, day, days);
  if (Math.abs(end - budget) <= budget * CLOSE) {
    return `On track: ${formatCents(spent)} spent so far. At this pace you'll spend about ${formatCents(end)} of your ` +
      `${formatCents(budget)} budget.`;
  }
  return end > budget
    ? `Spending faster than your budget: ${formatCents(spent)} so far. At this pace you'll spend about ` +
      `${formatCents(end)}, ${formatCents(end - budget)} over your ${formatCents(budget)} budget.`
    : `Under budget so far: ${formatCents(spent)} spent. At this pace you'll spend about ${formatCents(end)} of your ` +
      `${formatCents(budget)} budget, ${formatCents(budget - end)} less.`;
}

export function paceSentence(pace, percentBudgets = false) {
  const day = pace.days.length;
  if (!day) return "This month hasn't started yet.";
  const spent = pace.days[day - 1].spent_cents;
  const budget = pace.budget_cents;
  if (spent < 0) return `Refunds so far are bigger than your spending: ${formatCents(-spent)} back.`;
  if (budget <= 0) {
    return percentBudgets
      ? `You've spent ${formatCents(spent)} so far. Your budgets are shares of income, and no income has come in yet ` +
        "this month."
      : `You've spent ${formatCents(spent)} so far. Set budgets to see your pace.`;
  }
  const over = spent - budget;
  if (pace.complete) {
    return over > 0 ? `You spent ${formatCents(spent)}, ${formatCents(over)} over your ${formatCents(budget)} budget.`
      : `You spent ${formatCents(spent)} of your ${formatCents(budget)} budget.`;
  }
  if (over > 0) return `You've spent ${formatCents(spent)} so far, already ${formatCents(over)} over your ` +
    `${formatCents(budget)} budget.`;
  if (day < EARLY_DAYS) {
    return `So far you've spent ${formatCents(spent)} of your ${formatCents(budget)} budget. It's early in the month, ` +
      "and big bills like rent make spending look fast at first.";
  }
  return heading(spent, budget, day, pace.days_in_month);
}
