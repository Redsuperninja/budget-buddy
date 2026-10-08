// Suggested budget: a 50/30/20 plan from the last 3 months, and buttons to use it.

import { applySuggestion, budgetSuggestion } from "../api/endpoints.js";
import { currentMonth } from "../dates.js";
import { fill, h } from "../dom.js";
import { groupLabel } from "../labels.js";
import { formatCents } from "../money.js";
import { formatBp } from "../percent.js";
import { reload } from "../router.js";
import { card, empty, note, table } from "../widgets.js";

const share = (bp) => (bp === null ? "" : formatBp(bp));

function useButtons(month) {
  const message = h("span", { class: "muted" });
  const use = (choice, label) => h("button", { class: "primary", type: "button", onclick: async (event) => {
    event.target.disabled = true;
    try {
      await applySuggestion({ month, use: choice });
      await reload({ month });
    } catch (err) {
      message.textContent = ` ${err.message}`;
      event.target.disabled = false;
    }
  } }, label);
  return h("p", {}, use("amounts", "Use as dollar amounts"), " ", use("percentages", "Use as percentages of income"), message);
}

export async function render(root, options) {
  const month = options.month || currentMonth();
  const s = await budgetSuggestion(month);
  const incomeText = s.income_source === "planned"
    ? `Your planned income: ${formatCents(s.income_cents)} a month.`
    : `Your average income: ${formatCents(s.income_cents)} a month.`;
  fill(root,
    card(`Suggested budget for ${s.month}`,
      empty(`Built from ${s.looked_at[0]} to ${s.looked_at[s.looked_at.length - 1]} ` +
        `(${s.months_with_data} month(s) with activity). ${incomeText}`),
      empty("It follows the 50/30/20 guide: about half for needs, 30% for wants and 20% for savings. Needs keep " +
        "what you really spend; wants get what's left, up to 30%; the rest goes to savings."),
      s.notes.map((text) => note(text)),
      table(["Group", "Guide", "Average", "Suggested", "Share of income"],
        s.groups.map((g) => [groupLabel(g.group), formatBp(g.guide_percent_bp), formatCents(g.average_cents),
          formatCents(g.suggested_cents), share(g.suggested_percent_bp)]), [1, 2, 3, 4])),
    card("By category",
      table(["Category", "Group", "Average", "Budget now", "Suggested", "Share of income"],
        s.categories.map((c) => [c.name, groupLabel(c.group), formatCents(c.average_cents),
          formatCents(c.current_budget_cents), formatCents(c.suggested_cents), share(c.suggested_percent_bp)]),
        [2, 3, 4, 5]),
      empty("Using the suggestion replaces the budget of every needs, wants and savings category. " +
        "You can still change any of them afterwards on the Categories page."),
      s.savings_by_transfer_cents
        ? empty(`The plan also has ${formatCents(s.savings_by_transfer_cents)} a month to move into your savings ` +
            "accounts, like you've been doing. That isn't a category, so it isn't saved as a budget.")
        : null,
      s.income_source === "average"
        ? empty("Using it as percentages also saves your average income as your planned monthly income, " +
            "so the percentages stay steady through the month.")
        : null,
      s.income_cents > 0 ? useButtons(s.month) : null),
  );
}
