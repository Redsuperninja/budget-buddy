// Categories: rename, change the monthly budget, add a new one.

import { api } from "../api.js";
import { card, empty, fill, form, h, saveWithNote, table } from "../dom.js";
import { GROUPS, groupLabel } from "../labels.js";
import { centsToInput, centsOrThrow, parseDollars } from "../money.js";
import { reload } from "../router.js";

function editableRow(c) {
  const name = h("input", { value: c.name, "aria-label": "Name", maxlength: 100 });
  const budget = h("input",
    { value: centsToInput(c.budget_cents), "aria-label": "Monthly budget", inputmode: "decimal" });
  const note = h("span", { class: "muted" });
  const save = h("button", { class: "plain", type: "button", onclick: () => saveWithNote(note, async () => {
    const cents = parseDollars(budget.value);
    if (cents === null || cents < 0) throw new Error("Please enter the budget as a number, like 250.00.");
    await api("PATCH", `/api/local/categories/${c.id}`, { json: { name: name.value, budget_cents: cents } });
  }) }, "Save");
  return [name, groupLabel(c.group), budget, h("span", {}, save, note)];
}

export async function render(root) {
  const categories = await api("GET", "/api/local/categories");
  fill(root,
    card("Categories",
      categories.length
        ? table(["Name", "Group", "Monthly budget ($)", ""], categories.map(editableRow))
        : empty("No categories yet."),
      empty("A category's group can't be changed once made. A budget applies to every month.")),
    card("Add a category", form([
      { name: "name", label: "Name", required: true, maxlength: 100 },
      { name: "group", label: "Group", options: GROUPS },
      { name: "budget", label: "Monthly budget in dollars", value: "0", inputmode: "decimal" },
    ], "Add category", async (v) => {
      const budgetCents = centsOrThrow(v.budget || "0", "budget");
      await api("POST", "/api/local/categories", { json: { name: v.name, group: v.group, budget_cents: budgetCents } });
      await reload();
    })),
  );
}
