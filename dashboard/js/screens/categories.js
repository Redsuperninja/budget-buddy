// Categories: rename, change the monthly budget, add a new one.

import { createCategory, listCategories, updateCategory } from "../api/endpoints.js";
import { fill, h } from "../dom.js";
import { form, saveWithNote } from "../form.js";
import { card, empty, table } from "../widgets.js";
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
    await updateCategory(c.id, { name: name.value, budget_cents: cents });
  }) }, "Save");
  return [name, groupLabel(c.group), budget, h("span", {}, save, note)];
}

export async function render(root) {
  const categories = await listCategories();
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
      await createCategory({ name: v.name, group: v.group, budget_cents: budgetCents });
      await reload();
    })),
  );
}
