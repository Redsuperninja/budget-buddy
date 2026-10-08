// Home: the month at a glance, account balances, each group's share of income, and budget versus
// actual by category.

import { listAccounts, monthlySummary } from "../api/endpoints.js";
import { currentMonth } from "../dates.js";
import { fill, h } from "../dom.js";
import { card, empty, note, statCard, table } from "../widgets.js";
import { groupLabel, kindLabel } from "../labels.js";
import { formatBalance, formatCents } from "../money.js";
import { formatBp, percentUsed } from "../percent.js";
import { reload } from "../router.js";

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

function groupsCard(summary) {
  const rows = summary.groups.filter((g) => g.group !== "income").map((g) => [
    groupLabel(g.group), formatCents(g.budget_cents), formatCents(g.actual_cents),
    g.percent_of_income_bp === null ? "" : formatBp(g.percent_of_income_bp),
  ]);
  return card("Needs, wants and savings",
    table(["Group", "Budget", "Actual", "Share of income received"], rows, [1, 2, 3]),
    empty("A common guide is about 50% needs, 30% wants and 20% savings."));
}

export async function render(root, options) {
  const month = options.month || currentMonth();
  const [summary, accounts] = await Promise.all([
    monthlySummary(month),
    listAccounts(),
  ]);
  const picker = h("input", { type: "month", value: summary.month, "aria-label": "Month" });
  picker.addEventListener("change", () => { if (picker.value) reload({ month: picker.value }); });
  const hasPercent = summary.categories.some((c) => c.budget_percent_bp !== null);

  fill(root,
    h("div", { class: "toolbar" }, h("h2", {}, "Your month"), h("label", {}, "Month", picker)),
    h("div", { class: "cards" },
      statCard("Money in", formatCents(summary.income_cents)),
      statCard("Spent", formatCents(summary.spending_cents),
        h("div", { class: "muted" }, `Planned: ${formatCents(summary.spending_budget_cents)}`)),
      statCard("Saved", formatCents(summary.saved_cents), summary.saved_by_transfer_cents
        ? h("div", { class: "muted" }, `Moved to savings: ${formatCents(summary.saved_by_transfer_cents)}`) : null),
      statCard("Not sorted yet (money out)", formatCents(summary.unassigned_out_cents))),
    summary.unassigned_count
      ? note(`${summary.unassigned_count} transaction(s) have no category yet ` +
          `(${formatCents(summary.unassigned_out_cents)} out, ${formatCents(summary.unassigned_in_cents)} in). ` +
          "They are not counted above. Set a category on the Transactions page, or add an Auto-sort rule.")
      : null,
    groupsCard(summary),
    card("Account balances", accounts.length
      ? table(["Account", "Type", "Balance"],
          accounts.map((a) => [a.name, kindLabel(a.kind), formatBalance(a.balance_cents, a.kind)]), [2])
      : empty("No accounts yet. Add one on the Accounts page.")),
    card("Budget and actual by category", summary.categories.length
      ? table(["Category", "Group", "Budget (monthly)", "Actual this month", "Used"],
          summary.categories.map((c) =>
            [c.name, groupLabel(c.group), budgetCell(c), formatCents(c.actual_cents), used(c)]), [2, 3, 4])
      : empty("No categories yet."),
      hasPercent ? empty(incomeBasis(summary)) : null),
    empty("Budgets are the same every month, so changing one also changes how past months look."),
  );
}
