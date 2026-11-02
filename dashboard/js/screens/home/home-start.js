// Home's "Get started" checklist for someone new: add accounts, bring in transactions, set budgets, (on this
// computer) save the recovery phrase and make a backup, and (if they like) use a phone. Shown until the first three
// and the two safety steps are done; each step links to the page that does it.

import { saveSetup } from "../../api/endpoints.js";
import { fill, h } from "../../dom.js";
import { phoneStepLinks } from "../../features.js";
import { reload } from "../../router.js";
import { card } from "../../widgets.js";

const step = (done, title, links) => h("li", { class: done ? "done" : null },
  h("span", { class: "step-mark", "aria-hidden": "true" }, done ? "Done" : "To do"),
  h("span", {}, h("strong", {}, title), " ", links.map(([href, text], i) =>
    [i ? " or " : "", h("a", { href }, text)])));

// Only you know you wrote the phrase down, so this step has a button. The page redraws so the list updates.
function phraseStep(done) {
  const item = step(done, "Save your recovery phrase.", [["#backups", "Show it and write it down"]]);
  if (done) return item;
  const button = h("button", { type: "button" }, "I've written it down");
  const status = h("span", { class: "muted", role: "status" });
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await saveSetup({ phrase_saved: true });
      reload();
    } catch {
      button.disabled = false;
      fill(status, "That didn't save. Try again.");
    }
  });
  item.append(" ", button, " ", status);
  return item;
}

// setup is GET /api/local/setup, or null (a joined device, or no answer): then there are no safety steps.
export const safetyOpen = (setup) => Boolean(setup) && (!setup.phrase_saved_at || !setup.last_backup_at);

const COUNT_WORDS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six"];

// has: { accounts, transactions, budgets } (true once there is at least one).
// where: { onThisComputer } (a joined phone or computer has no Devices section, so no phone, phrase or backup step).
// setup: { phrase_saved_at, last_backup_at } from the Home Base, or null.
export function startCard(has, where, setup = null) {
  const safety = Boolean(where.onThisComputer && setup);
  if (has.accounts && has.transactions && has.budgets && !(safety && safetyOpen(setup))) return null;
  const phoneLinks = phoneStepLinks(where);
  const count = 3 + (safety ? 2 : 0) + (phoneLinks ? 1 : 0);
  return card("Get started",
    h("p", { class: "muted" }, `${COUNT_WORDS[count]} steps, about 15 minutes. Everything stays on this computer.`),
    h("ol", { class: "steps" },
      step(has.accounts, "Add your accounts.", [["#accounts", "Add checking, savings and cards"]]),
      step(has.transactions, "Bring in what you spent.", [["#import", "Import a file from your bank"],
        ["#transactions", "type them in"]]),
      step(has.budgets, "Set monthly budgets.", [["#plan", "Get a suggested budget"],
        ["#categories", "type your own"]]),
      safety && phraseStep(Boolean(setup.phrase_saved_at)),
      safety && step(Boolean(setup.last_backup_at), "Make a backup.", [["#backups", "Save a copy of your data"]]),
      phoneLinks && step(false, "Optional: use it on your phone.", phoneLinks)));
}
