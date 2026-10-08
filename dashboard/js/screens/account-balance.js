// Part of the Accounts screen: "Match your bank's balance". Today's balance from the bank, or the balance at the
// start of the year; Budget Buddy adds one balance adjustment for the difference (not income or spending).

import { setAccountBalance } from "../api/endpoints.js";
import { today } from "../dates.js";
import { h } from "../dom.js";
import { accountField } from "../fields.js";
import { form } from "../form.js";
import { bankBalanceToCents, formatBalance } from "../money.js";
import { reload } from "../router.js";
import { card, empty } from "../widgets.js";

// The last day of last year: the balance then is the balance at the start of this year.
const startOfYear = () => `${Number(today().slice(0, 4)) - 1}-12-31`;

function chosenDate(v) {
  if (v.when === "start") return startOfYear();
  if (v.when === "date") {
    if (!v.date) throw new Error("Pick the day for the balance.");
    return v.date;
  }
  return today();
}

// done: what the last save did (shown after the page redraws), or undefined.
export function balanceCard(accounts, done) {
  const kinds = new Map(accounts.map((a) => [String(a.id), a.kind]));
  return card("Match your bank's balance",
    empty("Type the balance your bank shows. Budget Buddy adds one \"balance adjustment\" for any difference, so " +
      "the balance here matches. Adjustments aren't counted as income or spending."),
    form([
      accountField(accounts),
      { name: "when", label: "Balance on", options: [
        ["today", "Today (from your bank's website or app)"],
        ["start", "The start of this year (your balance at the end of December 31)"],
        ["date", "Another day (pick below)"],
      ] },
      { name: "date", label: "The day, if another day", type: "date" },
      { name: "balance", required: true, inputmode: "decimal",
        label: "Balance in dollars (card or loan: what you owe; a minus sign if it owes you)" },
    ], "Set balance", async (v) => {
      const kind = kinds.get(v.account_id);
      const saved = await setAccountBalance(Number(v.account_id), {
        date: chosenDate(v), balance_cents: bankBalanceToCents(v.balance, kind),
      });
      const now = `Your balance today is ${formatBalance(saved.balance_now_cents, kind)}.`;
      await reload({ balanceDone: saved.adjustment_cents
        ? `Done: the balance on ${saved.date} now matches your bank. ${now}`
        : `It already matched, so nothing was added. ${now}` });
    }),
    done ? h("p", { class: "ok", role: "status" }, done) : null);
}
