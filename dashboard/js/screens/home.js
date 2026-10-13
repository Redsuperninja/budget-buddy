// Home: a "Get started" checklist for someone new (home-start.js), the month at a glance (money tiles with a small
// trend line each, and what needs you), where the income went, spending against budget, spending against last month,
// month by month, and what you have and owe. Every chart can also be read as a table.

import {
  listAccounts, listPositions, listTransactions, monthlySummary, monthlyTrend, payDeposits, stockHoldings,
} from "../api/endpoints.js";
import { comparedWith, fromFirstActivity } from "../charts/months.js";
import { currentMonth, today } from "../dates.js";
import { fill, h } from "../dom.js";
import { empty, table } from "../widgets.js";
import { groupLabel } from "../labels.js";
import { formatCents } from "../money.js";
import { formatBp, percentUsed } from "../percent.js";
import { reload } from "../router.js";
import { categoriesChart, changesChart, groupsChart, trendChart } from "./home-charts.js";
import { balancesCard, incomeSplitCard } from "./home-overview.js";
import { startCard } from "./home-start.js";
import { attentionCard, monthTiles } from "./home-tiles.js";

const used = (c) => {
  const pct = percentUsed(c.actual_cents, c.budget_cents);
  return pct === null ? "" : `${pct}%`;
};

const budgetCell = (c) =>
  c.budget_percent_bp === null ? formatCents(c.budget_cents) : `${formatCents(c.budget_cents)} (${formatBp(c.budget_percent_bp)})`;

const incomeBasis = (s) => (s.budget_income_source === "planned"
  ? `Percentage budgets are shares of your planned income, ${formatCents(s.budget_income_cents)} a month.`
  : `Percentage budgets are shares of this month's income, ${formatCents(s.budget_income_cents)}. ` +
    "Set a planned monthly income on the Categories page to keep them steady.");

// Income isn't budgeted: it's what the budgets are measured against, shown in "Money in" above.
function budgetTable(summary) {
  const budgeted = summary.categories.filter((c) => c.group !== "income");
  if (!budgeted.length) return empty("No categories yet.");
  return h("div", {},
    table(["Category", "Group", "Budget (monthly)", "Actual this month", "Used"],
      budgeted.map((c) =>
        [c.name, groupLabel(c.group), budgetCell(c), formatCents(c.actual_cents), used(c)]), [2, 3, 4]),
    summary.categories.some((c) => c.budget_percent_bp !== null) ? empty(incomeBasis(summary)) : null);
}

export async function render(root, options) {
  const month = options.month || currentMonth();
  const days = comparedWith(month, today());
  const [summary, trend, accounts, waiting, deposits, positions, held, anyTransaction, soFar, before] = await Promise.all([
    monthlySummary(month),
    monthlyTrend(month),
    listAccounts(),
    listTransactions(new URLSearchParams({ uncategorized: "true", limit: "1" })),
    payDeposits(month.slice(0, 4)),
    listPositions(),
    stockHoldings(),
    listTransactions(new URLSearchParams({ limit: "1" })),
    days.through ? monthlySummary(month, days.through) : null,
    monthlySummary(days.previous, days.previousThrough),
  ]);
  const months = fromFirstActivity(trend.months);
  const picker = h("input", { type: "month", value: summary.month, "aria-label": "Month" });
  picker.addEventListener("change", () => { if (picker.value) reload({ month: picker.value }); });
  const mismatched = positions.accounts.flatMap((a) => a.positions).filter((p) => !p.matches).length;

  // Until the first transaction there is nothing to chart: the checklist says what to do first.
  const hasTransactions = anyTransaction.total > 0;
  fill(root,
    startCard({ accounts: accounts.length > 0, transactions: hasTransactions,
      budgets: summary.categories.some((c) => c.group !== "income" && c.budget_cents > 0) }),
    h("div", { class: "toolbar" }, h("h2", {}, "Your month"), h("label", {}, "Month", picker)),
    // While the month is going, its own point would dip (a part month): the tiles' lines show the months before it.
    monthTiles(summary, days.through ? months.slice(0, -1) : months),
    hasTransactions && attentionCard([
      { count: waiting.total, href: "#transactions?sorted=none",
        text: waiting.total === 1 ? "transaction needs a category" : "transactions need a category" },
      { count: deposits.length, href: "#paychecks",
        text: deposits.length === 1 ? "pay deposit to fill in on Paychecks" : "pay deposits to fill in on Paychecks" },
      { count: mismatched, href: "#investments", text: mismatched === 1
        ? "position doesn't match your recorded trades" : "positions don't match your recorded trades" },
    ]),
    hasTransactions && [
      incomeSplitCard(summary),
      groupsChart(summary),
      categoriesChart(summary, budgetTable(summary)),
      changesChart(soFar || summary, before, days),
      trendChart(months),
      balancesCard(accounts, held.accounts.length ? held.value_cents : null),
      empty("Budgets are the same every month, so changing one also changes how past months look."),
    ],
  );
}
