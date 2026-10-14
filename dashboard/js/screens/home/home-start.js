// Home's "Get started" checklist for someone new: add accounts, bring in transactions, set budgets, and (if they
// like) connect a phone. Shown until the first three are done; each step links to the page that does it.

import { h } from "../../dom.js";
import { card } from "../../widgets.js";

const step = (done, title, links) => h("li", { class: done ? "done" : null },
  h("span", { class: "step-mark", "aria-hidden": "true" }, done ? "Done" : "To do"),
  h("span", {}, h("strong", {}, title), " ", links.map(([href, text], i) =>
    [i ? " or " : "", h("a", { href }, text)])));

// has: { accounts, transactions, budgets } (true once there is at least one).
export function startCard(has) {
  if (has.accounts && has.transactions && has.budgets) return null;
  return card("Get started",
    h("p", { class: "muted" }, "Four steps, about 15 minutes. Everything stays on this computer."),
    h("ol", { class: "steps" },
      step(has.accounts, "Add your accounts.", [["#accounts", "Add checking, savings and cards"]]),
      step(has.transactions, "Bring in what you spent.", [["#import", "Import a file from your bank"],
        ["#transactions", "type them in"]]),
      step(has.budgets, "Set monthly budgets.", [["#plan", "Get a suggested budget"],
        ["#categories", "type your own"]]),
      step(false, "Optional: use it on your phone.", [["#phone", "Connect the phone app"],
        ["#computers", "open it in your phone's web browser"]])));
}
