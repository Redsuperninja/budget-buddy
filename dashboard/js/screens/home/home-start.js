// Home's "Get started" checklist for someone new: add accounts, bring in transactions, set budgets, and (if they
// like) connect a phone. Shown until the first three are done; each step links to the page that does it.

import { h } from "../../dom.js";
import { phoneStepLinks } from "../../features.js";
import { card } from "../../widgets.js";

const step = (done, title, links) => h("li", { class: done ? "done" : null },
  h("span", { class: "step-mark", "aria-hidden": "true" }, done ? "Done" : "To do"),
  h("span", {}, h("strong", {}, title), " ", links.map(([href, text], i) =>
    [i ? " or " : "", h("a", { href }, text)])));

// has: { accounts, transactions, budgets } (true once there is at least one).
// where: { onThisComputer } (a joined phone or computer has no Devices section, so no phone step).
export function startCard(has, where) {
  if (has.accounts && has.transactions && has.budgets) return null;
  const phoneLinks = phoneStepLinks(where);
  return card("Get started",
    h("p", { class: "muted" }, `${phoneLinks ? "Four" : "Three"} steps, about 15 minutes. Everything stays on this computer.`),
    h("ol", { class: "steps" },
      step(has.accounts, "Add your accounts.", [["#accounts", "Add checking, savings and cards"]]),
      step(has.transactions, "Bring in what you spent.", [["#import", "Import a file from your bank"],
        ["#transactions", "type them in"]]),
      step(has.budgets, "Set monthly budgets.", [["#plan", "Get a suggested budget"],
        ["#categories", "type your own"]]),
      phoneLinks && step(false, "Optional: use it on your phone.", phoneLinks)));
}
