// Home: the month at a glance, account balances, and budget versus actual by category.

import { listAccounts, monthlySummary } from "../api/endpoints.js";
import { currentMonth } from "../dates.js";
import { fill, h } from "../dom.js";
import { card, empty, note, statCard, table } from "../widgets.js";
import { groupLabel, kindLabel } from "../labels.js";
import { formatBalance, formatCents } from "../money.js";
import { reload } from "../router.js";

export async function render(root, options) {
  const month = options.month || currentMonth();
  const [summary, accounts] = await Promise.all([
    monthlySummary(month),
    listAccounts(),
  ]);
  const picker = h("input", { type: "month", value: summary.month, "aria-label": "Month" });
  picker.addEventListener("change", () => { if (picker.value) reload({ month: picker.value }); });

  fill(root,
    h("div", { class: "toolbar" }, h("h2", {}, "Your month"), h("label", {}, "Month", picker)),
    h("div", { class: "cards" },
      statCard("Money in", formatCents(summary.income_cents)),
      statCard("Spent", formatCents(summary.spending_cents),
        h("div", { class: "muted" }, `Planned: ${formatCents(summary.spending_budget_cents)}`)),
      statCard("Saved", formatCents(summary.saved_cents)),
      statCard("Not sorted yet (money out)", formatCents(summary.unassigned_out_cents))),
    summary.unassigned_count
      ? note(`${summary.unassigned_count} transaction(s) have no category yet ` +
          `(${formatCents(summary.unassigned_out_cents)} out, ${formatCents(summary.unassigned_in_cents)} in). ` +
          "They are not counted above. Set a category on the Transactions page.")
      : null,
    card("Account balances", accounts.length
      ? table(["Account", "Type", "Balance"],
          accounts.map((a) => [a.name, kindLabel(a.kind), formatBalance(a.balance_cents, a.kind)]), [2])
      : empty("No accounts yet. Add one on the Accounts page.")),
    card("Budget and actual by category", summary.categories.length
      ? table(["Category", "Group", "Budget (monthly)", "Actual this month"],
          summary.categories.map((c) =>
            [c.name, groupLabel(c.group), formatCents(c.budget_cents), formatCents(c.actual_cents)]), [2, 3])
      : empty("No categories yet.")),
    empty("Budgets are the same every month, so changing one also changes how past months look."),
  );
}
