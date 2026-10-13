// The charts on Home: needs/wants/savings against budget, spending categories against budget, spending against
// last month, and money in, spending and saving month by month. Each can switch to a table.

import { budgetBars } from "../charts/budget-bars.js";
import { progressRows } from "../charts/progress-rows.js";
import { changeBars, changeText } from "../charts/change-bars.js";
import { chartCard } from "../charts/chart-card.js";
import { lineChart } from "../charts/line-chart.js";
import { dayOfMonth, hasMoney, spendingChanges } from "../charts/months.js";
import { monthLabel, monthName } from "../dates.js";
import { groupLabel } from "../labels.js";
import { formatCents } from "../money.js";
import { formatBp } from "../percent.js";
import { card, empty, table } from "../widgets.js";

const share = (bp) => (bp === null ? "" : formatBp(bp));

export function groupsChart(summary) {
  const groups = summary.groups.filter((g) => g.group !== "income");
  const rows = groups.map((g) => ({ label: groupLabel(g.group), actual: g.actual_cents, budget: g.budget_cents }));
  return chartCard("Needs, wants and savings", {
    chart: budgetBars(rows, "Spent in each group this month, with its budget marked"),
    table: table(["Group", "Budget", "Actual", "Share of income received"], groups.map((g) =>
      [groupLabel(g.group), formatCents(g.budget_cents), formatCents(g.actual_cents), share(g.percent_of_income_bp)]),
      [1, 2, 3]),
    note: empty("Bars show what you spent or saved; the short upright line is the budget. A common guide is about 50% needs, " +
      "30% wants and 20% savings."),
  });
}

// provisional: the month is going and percentage budgets follow the pay received so far (category-groups budgetWords).
export function categoriesChart(summary, budgetTable, provisional = false) {
  const rows = summary.categories
    .filter((c) => c.group !== "income" && (c.budget_cents > 0 || c.actual_cents !== 0))
    .map((c) => ({ label: c.name, actual: c.actual_cents, budget: c.budget_cents, saving: c.group === "savings",
      percent_bp: c.budget_percent_bp,
      href: `#transactions?category=${c.category_id}&month=${summary.month}` }));
  return chartCard("Budget and actual by category", {
    chart: rows.length ? progressRows(rows, { provisional }) : empty("Nothing spent or budgeted yet this month."),
    table: budgetTable,
    note: empty("Click a category to see its transactions."),
  });
}

// months: the trend from its first month with anything in it (months.js fromFirstActivity), at most 12.
export function trendChart(months) {
  const labels = months.map((m) => monthLabel(m.month));
  const series = [
    { name: "Money in", values: months.map((m) => m.income_cents) },
    { name: "Spent", values: months.map((m) => m.spending_cents) },
    { name: "Saved", values: months.map((m) => m.saved_cents) },
  ];
  return chartCard("Month by month", {
    chart: lineChart(series, labels, `Money in, spending and saving for each of the last ${months.length} months`),
    legendNames: series.map((sr) => sr.name),
    table: table(["Month", ...series.map((sr) => sr.name)], months.map((m, i) =>
      [labels[i], formatCents(m.income_cents), formatCents(m.spending_cents), formatCents(m.saved_cents)]), [1, 2, 3]),
    note: empty(`${months.length === 1 ? "Your first month" : `The last ${months.length} months`}. ` +
      "Point at a month to see its numbers."),
  });
}

// Spending in each category against last month: the same days of it while this month is still going.
// days: comparedWith(...) from months.js.
export function changesChart(current, previous, days) {
  const lastName = monthName(days.previous);
  let which = `this month against ${lastName}`;
  if (days.through && days.through.endsWith("-01")) which = `the 1st of this month against the 1st of ${lastName}`;
  else if (days.through) {
    which = `the 1st to the ${dayOfMonth(days.through)} of this month against the same days of ${lastName}` +
      (days.previousThrough.slice(8) < days.through.slice(8) ? ` (up to the ${dayOfMonth(days.previousThrough)})` : "");
  }
  // Last month with no money in it (the first month you used Budget Buddy) would make everything look like "more".
  if (!hasMoney(previous)) {
    return card("Compared with last month", empty(`Nothing to compare with yet: ${lastName} has no transactions.`));
  }
  const rows = spendingChanges(current, previous);
  const unsorted = current.unassigned_out_cents || previous.unassigned_out_cents
    ? " Spending without a category isn't included: give it one on the Transactions page." : "";
  return chartCard("Compared with last month", {
    chart: rows.length ? changeBars(rows, `How spending in each category changed: ${which}`)
      : empty("Spending in every category you've sorted is the same as last month."),
    table: table(["Category", "Change"], rows.map((r) => [r.label, changeText(r.cents)]), [1]),
    note: empty(`Needs and wants: ${which}. Bars to the right mean you spent more, to the left less.${unsorted}`),
  });
}
