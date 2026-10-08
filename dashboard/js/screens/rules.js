// Auto-sort rules: "a description containing this text goes in this category". Shows which rules Budget Buddy
// learned from your choices, how many transactions each sorted, and the latest auto-sorted transactions.

import { applyRules, createRule, deleteRule, listCategories, listRules, listTransactions } from "../api/endpoints.js";
import { fill, h } from "../dom.js";
import { categoryField, idOrNull } from "../fields.js";
import { form, saveWithNote } from "../form.js";
import { reload } from "../router.js";
import { formatCents } from "../money.js";
import { card, empty, table } from "../widgets.js";
import { categoryPicker } from "./category-picker.js";

const SHOWN = 100;

function ruleRow(rule, categoryName) {
  const note = h("span", { class: "muted" });
  const remove = h("button", { class: "plain", type: "button", onclick: () => saveWithNote(note, async () => {
    await deleteRule(rule.id);
    await reload();
  }) }, "Remove");
  return [rule.pattern, categoryName(rule.category_id), rule.learned ? "Learned from your choices" : "Added by you",
    String(rule.sorted_count), h("span", {}, remove, note)];
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

function autoSortedCard(page, rules, categories) {
  const patterns = new Map(rules.map((r) => [r.id, r.pattern]));
  return card("Auto-sorted transactions",
    empty("Everything a rule sorted, newest first. Change a category here if a rule got it wrong; " +
      "that counts as your choice from then on."),
    page.items.length
      ? table(["Date", "What", "Amount", "Category", "By the rule"], page.items.map((t) =>
          [t.date, t.description, formatCents(t.amount_cents), categoryPicker(t, categories),
            patterns.get(t.sorted_by_rule_id) || "(a removed rule)"]), [2])
      : empty("Nothing has been auto-sorted yet."),
    page.total > page.items.length
      ? empty(`Showing the newest ${page.items.length} of ${page.total}. On the Transactions page, set ` +
          "\"Category set\" to Auto-sorted to see them by month.") : null);
}

export async function render(root) {
  const [rules, categories, autoSorted] = await Promise.all([
    listRules(), listCategories(), listTransactions(new URLSearchParams({ sorted_by: "rule", limit: String(SHOWN) })),
  ]);
  const names = new Map(categories.map((c) => [c.id, c.name]));
  const categoryName = (id) => names.get(id) || "";
  fill(root,
    card("Auto-sort rules",
      empty("When a transaction's description contains the text of a rule, it goes in that category. " +
        "Upper and lower case don't matter. If more than one rule fits, the longest text wins."),
      empty("Budget Buddy also learns: after you pick the same category three times for the same shop, " +
        "it adds a rule for it."),
      rules.length
        ? table(["Description contains", "Category", "Made", "Sorted", ""], rules.map((r) => ruleRow(r, categoryName)), [3])
        : empty("No rules yet."),
      empty("Rules sort new bank-file rows and new transactions added without a category. " +
        "They never change a category you picked. To sort older transactions that have no category yet:"),
      sortNowButton()),
    autoSortedCard(autoSorted, rules, categories),
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
