// The charts on Home: needs/wants/savings against budget, spending categories against budget, and the
// last 12 months of money in, spending and saving. Each can switch to a table.

import { budgetBars } from "../charts/budget-bars.js";
import { chartCard } from "../charts/chart-card.js";
import { lineChart } from "../charts/line-chart.js";
import { monthLabel } from "../dates.js";
import { groupLabel } from "../labels.js";
import { formatCents } from "../money.js";
import { formatBp } from "../percent.js";
import { empty, table } from "../widgets.js";

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

export function categoriesChart(summary, budgetTable) {
  const rows = summary.categories
    .filter((c) => c.group !== "income" && (c.budget_cents > 0 || c.actual_cents !== 0))
    .map((c) => ({ label: c.name, actual: c.actual_cents, budget: c.budget_cents }));
  return chartCard("Budget and actual by category", {
    chart: rows.length ? budgetBars(rows, "Spent in each category this month, with its budget marked")
      : empty("Nothing spent or budgeted yet this month."),
    table: budgetTable,
  });
}

export function trendChart(trend) {
  const labels = trend.months.map((m) => monthLabel(m.month));
  const series = [
    { name: "Money in", values: trend.months.map((m) => m.income_cents) },
    { name: "Spent", values: trend.months.map((m) => m.spending_cents) },
    { name: "Saved", values: trend.months.map((m) => m.saved_cents) },
  ];
  return chartCard("The last 12 months", {
    chart: lineChart(series, labels, "Money in, spending and saving for each of the last 12 months"),
    legendNames: series.map((sr) => sr.name),
    table: table(["Month", ...series.map((sr) => sr.name)], trend.months.map((m, i) =>
      [labels[i], formatCents(m.income_cents), formatCents(m.spending_cents), formatCents(m.saved_cents)]), [1, 2, 3]),
    note: empty("Point at a month to see its numbers."),
  });
}
