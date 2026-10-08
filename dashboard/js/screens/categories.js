// Categories: rename, change the monthly budget (an amount or a percentage of income), add a new
// one, and the planned monthly income that percentages are shares of.

import { createCategory, getBudgetPlan, listCategories, saveBudgetPlan, updateCategory } from "../api/endpoints.js";
import { fill, h } from "../dom.js";
import { form, saveWithNote } from "../form.js";
import { card, empty, note, table } from "../widgets.js";
import { GROUPS, groupLabel } from "../labels.js";
import { centsToInput, formatCents, parseDollars } from "../money.js";
import { formatBp, parsePercent } from "../percent.js";
import { reload } from "../router.js";

const BUDGET_HELP = "Please enter the budget as an amount, like 250.00, or a percentage of income, like 15%.";

// "250.00" -> { budget_cents }, "15%" -> { budget_percent_bp }.
function budgetBody(text) {
  const t = String(text).trim() || "0";
  if (t.endsWith("%")) {
    const bp = parsePercent(t);
    if (bp === null || bp < 1 || bp > 10000) throw new Error("Please enter a percentage from 0.01% to 100%.");
    return { budget_percent_bp: bp };
  }
  const cents = parseDollars(t);
  if (cents === null || cents < 0) throw new Error(BUDGET_HELP);
  return { budget_cents: cents };
}

const budgetText = (c) => (c.budget_percent_bp !== null ? formatBp(c.budget_percent_bp) : centsToInput(c.budget_cents));

function editableRow(c) {
  const name = h("input", { value: c.name, "aria-label": "Name", maxlength: 100 });
  const budget = h("input", { value: budgetText(c), "aria-label": "Monthly budget", inputmode: "decimal" });
  const note = h("span", { class: "muted" });
  const save = h("button", { class: "plain", type: "button", onclick: () => saveWithNote(note, async () => {
    await updateCategory(c.id, { name: name.value, ...budgetBody(budget.value) });
  }) }, "Save");
  return [name, groupLabel(c.group), budget, h("span", {}, save, note)];
}

function percentTotalNote(categories) {
  const total = categories.reduce((sum, c) => sum + (c.budget_percent_bp || 0), 0);
  if (total > 10000) return note(`Your percentage budgets add up to ${formatBp(total)} of income, which is more than you earn.`);
  return total ? empty(`Percentage budgets add up to ${formatBp(total)} of income.`) : null;
}

function plannedIncomeCard(plan) {
  const planned = plan.planned_income_cents;
  return card("Planned monthly income",
    empty("Percentage budgets are a share of this amount: your take-home pay in a usual month. " +
      "Leave it empty to use what actually came in each month instead."),
    empty(planned === null ? "Not set: percentages follow each month's actual income." : `Now: ${formatCents(planned)} a month.`),
    form([
      { name: "income", label: "Take-home pay per month (empty to clear)", value: planned === null ? "" : centsToInput(planned),
        inputmode: "decimal" },
    ], "Save income", async (v) => {
      const text = v.income.trim();
      const cents = text === "" ? null : parseDollars(text);
      if (text !== "" && (cents === null || cents < 0)) throw new Error("Please enter the income as a number, like 4000.00.");
      await saveBudgetPlan({ planned_income_cents: cents });
      await reload();
    }));
}

export async function render(root) {
  const [categories, plan] = await Promise.all([listCategories(), getBudgetPlan()]);
  fill(root,
    card("Categories",
      categories.length
        ? table(["Name", "Group", "Monthly budget ($ or %)", ""], categories.map(editableRow))
        : empty("No categories yet."),
      percentTotalNote(categories),
      empty("Type an amount like 250.00, or a percentage of income like 15%. Income categories take amounts only. " +
        "A category's group can't be changed once made. A budget applies to every month.")),
    plannedIncomeCard(plan),
    card("Add a category", form([
      { name: "name", label: "Name", required: true, maxlength: 100 },
      { name: "group", label: "Group", options: GROUPS },
      { name: "budget", label: "Monthly budget ($ or %)", value: "0", inputmode: "decimal" },
    ], "Add category", async (v) => {
      await createCategory({ name: v.name, group: v.group, ...budgetBody(v.budget) });
      await reload();
    })),
  );
}
