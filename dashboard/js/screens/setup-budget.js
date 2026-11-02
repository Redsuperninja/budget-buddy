// The Starter budget card of the Setup page (roadmap 25h): untick starter categories you don't need, and
// optionally enter monthly take-home pay as planned income. Saving is one button; skipping is leaving it alone.

import { deleteCategory, getBudgetPlan, listCategories, saveBudgetPlan } from "../api/endpoints.js";
import { fill, h, showError } from "../dom.js";
import { groupLabel } from "../labels.js";
import { centsToInput } from "../money.js";
import { choosable, savedSummary, takeHomeFromText, toRemove } from "../setup-budget.js";
import { card } from "../widgets.js";

// Remove each id; one something uses is kept (the Home Base says 409). Returns { removed, kept } (id lists).
async function removeAll(ids) {
  const removed = [];
  const kept = [];
  for (const id of ids) {
    try {
      await deleteCategory(id);
      removed.push(id);
    } catch (err) {
      if (err.status !== 409) throw err;
      kept.push(id);
    }
  }
  return { removed, kept };
}

export async function starterBudgetCard(title) {
  const [categories, plan] = await Promise.all([listCategories(), getBudgetPlan()]);
  const boxes = new Map();
  const groups = choosable(categories).map(({ group, categories: items }) => h("fieldset", {},
    h("legend", {}, groupLabel(group)),
    items.map((c) => {
      const box = h("input", { type: "checkbox", checked: true });
      boxes.set(c.id, box);
      return h("label", { class: "check" }, box, c.name);
    })));

  const pay = h("input", { type: "text", inputmode: "decimal", autocomplete: "off", placeholder: "for example 3200.00",
    value: plan.planned_income_cents === null ? "" : centsToInput(plan.planned_income_cents) });
  const result = h("div", { role: "status" });
  const save = h("button", { class: "primary", type: "button", onclick: async () => {
    const income = takeHomeFromText(pay.value);
    if (income.error) return fill(result, h("p", { class: "error", role: "alert" }, income.error));
    // Boxes already removed are disabled, so a second save never asks again.
    const unticked = new Set([...boxes].filter(([, box]) => !box.checked && !box.disabled).map(([id]) => id));
    save.disabled = true;
    try {
      const { removed, kept } = await removeAll(toRemove(categories, unticked));
      if (income.cents !== null) await saveBudgetPlan({ planned_income_cents: income.cents });
      fill(result, h("p", { class: "ok" },
        savedSummary({ removed: removed.length, kept: kept.length, income: income.cents })));
      for (const id of removed) boxes.get(id).disabled = true;
      for (const id of kept) boxes.get(id).checked = true;
    } catch (err) {
      showError(result, err);
    } finally {
      save.disabled = false;
    }
  } }, "Save starter budget");

  return card(title, h("p", { class: "muted" }, "Optional"),
    h("p", {}, "Budget Buddy starts you off with these categories. Untick the ones you won't use, and ",
      "Save starter budget removes them. A category that already has transactions is always kept. ",
      "You can add a category back later in Budget."),
    groups,
    h("label", {}, "Your take-home pay each month, after tax (optional)", pay),
    h("p", { class: "muted" }, "Used to turn percentage budgets into dollar amounts. Leave it blank to skip."),
    h("div", { class: "toolbar" }, save), result);
}
