// Auto-sort rules: "a description containing this text goes in this category".

import { applyRules, createRule, deleteRule, listCategories, listRules } from "../api/endpoints.js";
import { fill, h } from "../dom.js";
import { categoryField, idOrNull } from "../fields.js";
import { form, saveWithNote } from "../form.js";
import { reload } from "../router.js";
import { card, empty, table } from "../widgets.js";

function ruleRow(rule, categoryName) {
  const note = h("span", { class: "muted" });
  const remove = h("button", { class: "plain", type: "button", onclick: () => saveWithNote(note, async () => {
    await deleteRule(rule.id);
    await reload();
  }) }, "Remove");
  return [rule.pattern, categoryName(rule.category_id), h("span", {}, remove, note)];
}

function sortNowButton() {
  const note = h("span", { class: "muted" });
  const button = h("button", { class: "primary", type: "button", onclick: async () => {
    button.disabled = true;
    try {
      const r = await applyRules();
      note.textContent = ` ${r.categorized} transaction(s) sorted.`;
    } catch (err) {
      note.textContent = ` ${err.message}`;
    } finally {
      button.disabled = false;
    }
  } }, "Sort transactions now");
  return h("p", {}, button, note);
}

export async function render(root) {
  const [rules, categories] = await Promise.all([listRules(), listCategories()]);
  const names = new Map(categories.map((c) => [c.id, c.name]));
  const categoryName = (id) => names.get(id) || "";
  fill(root,
    card("Auto-sort rules",
      empty("When a transaction's description contains the text of a rule, it goes in that category. " +
        "Upper and lower case don't matter. If more than one rule fits, the longest text wins."),
      rules.length
        ? table(["Description contains", "Category", ""], rules.map((r) => ruleRow(r, categoryName)))
        : empty("No rules yet."),
      empty("Rules sort new bank-file rows and new transactions added without a category. " +
        "They never change a category you picked. To sort older transactions that have no category yet:"),
      sortNowButton()),
    card("Add a rule", form([
      { name: "pattern", label: "Description contains", required: true, maxlength: 100,
        placeholder: "GROCERY MART" },
      categoryField(categories),
    ], "Add rule", async (v) => {
      await createRule({ pattern: v.pattern, category_id: idOrNull(v.category_id) });
      await reload();
    })),
  );
}
