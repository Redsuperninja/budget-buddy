// The Setup page (roadmap 25f, ADR-0015): shown instead of Home on the first start on this computer. Every step is
// optional. "Finish later" goes Home (Get started carries what's left); "Done" remembers on the Home Base that
// setup is finished. The steps reuse the Backups restore, the recovery phrase card and the account/import pages.

import { getSetup, listAccounts, listTransactions, saveSetup } from "../api/endpoints.js";
import { fill, h, showError } from "../dom.js";
import { onThisComputer, phoneStepLinks } from "../features.js";
import { SKIPPED_KEY, stepsDone } from "../setup-steps.js";
import { card, note } from "../widgets.js";
import { phraseCard } from "./devices/recovery-phrase.js";

const mark = (done) => h("p", { class: done ? "ok" : "muted" }, done ? "Done" : "Optional");
const links = (pairs) => pairs.map(([href, text], i) => [i ? " or " : "", h("a", { href }, text)]);

function phraseStep(progress) {
  const status = h("span", { role: "status" });
  const tick = h("input", { type: "checkbox", checked: Boolean(progress.phrase_saved_at) });
  tick.addEventListener("change", async () => {
    tick.disabled = true;
    try {
      await saveSetup({ phrase_saved: tick.checked });
      fill(status, tick.checked ? "Saved. Thank you." : "");
    } catch (err) {
      tick.checked = !tick.checked;
      showError(status, err);
    } finally {
      tick.disabled = false;
    }
  });
  return [phraseCard(), h("label", {}, tick, " I've written it down"), " ", status];
}

export async function render(root) {
  if (!onThisComputer()) {
    fill(root, h("p", {}, "Setup is done on the Budget Buddy computer itself."), h("a", { href: "#home" }, "Go to Home"));
    return;
  }
  const [progress, accounts, transactions] = await Promise.all([
    getSetup(), listAccounts(), listTransactions(new URLSearchParams({ limit: "1" })),
  ]);
  const done = stepsDone(progress, { accounts: accounts.length, transactions: transactions.total });
  const result = h("div", {});
  const phone = phoneStepLinks({ onThisComputer: true });
  const leave = () => { location.hash = "home"; };

  const finish = h("button", { class: "primary", type: "button", onclick: async () => {
    finish.disabled = true;
    try {
      await saveSetup({ finished: true });
      leave();
    } catch (err) {
      finish.disabled = false;
      showError(result, err);
    }
  } }, "Done");
  const later = h("button", { type: "button", onclick: () => {
    try { sessionStorage.setItem(SKIPPED_KEY, "1"); } catch { /* storage blocked: Home still opens */ }
    leave();
  } }, "Finish later");

  fill(root,
    h("h2", {}, "Welcome to Budget Buddy"),
    h("p", { class: "muted" }, "A few quick steps. Every one is optional, and everything stays on this computer."),
    card("1. Start fresh, or bring a backup",
      h("p", {}, "New here? Just carry on with the next step. Moving from another computer? ",
        h("a", { href: "#backups" }, "Restore a backup"), " first."),
      note("A restore finishes the next time you start Budget Buddy.")),
    card("2. Save your recovery phrase", mark(done.phrase),
      h("p", {}, "Do this before you add anything. It's the one thing that can't be fixed later."),
      phraseStep(progress)),
    card("3. Your first account", mark(done.account),
      h("p", {}, links([["#accounts", "Add a checking, savings or card account"],
        ["#import", "import a file from your bank"]])),
      h("p", { class: "muted" }, "Add an account first; then a bank file can be imported into it.")),
    phone && card("4. Your phone", mark(false),
      h("p", {}, "To use Budget Buddy on your phone, ", links(phone), ".")),
    h("div", { class: "toolbar" }, finish, later),
    result);
}
