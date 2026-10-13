// Spending against budget as a list (the categories chart on Home): each category's name (a link to its
// transactions), what's left or how far over in words, a thin meter, and what was spent of the budget. Savings read
// as goals; a percentage budget mid-month is only "so far" (category-groups.js budgetWords has the wording).
// rows: [{ label, actual, budget, href, saving?, percent_bp? }] in cents. provisional: see budgetWords.

import { budgetWords } from "../category-groups.js";
import { h } from "../dom.js";
import { meter } from "./meter.js";

export function progressRows(rows, { provisional = false } = {}) {
  return h("ul", { class: "progress-rows" }, rows.map((r) => {
    const w = budgetWords(r, { provisional });
    return h("li", {},
      h("div", { class: "progress-head" }, h("a", { href: r.href }, r.label),
        h("span", { class: w.alarm ? "bad" : null }, w.right)),
      r.budget > 0 ? meter(w.used, `${r.label}: ${w.below}`, w.alarm) : null,
      h("div", { class: "muted" }, w.below));
  }));
}
