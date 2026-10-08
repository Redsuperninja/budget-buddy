// Part of the Accounts screen: "Match your bank's balance". Today's balance from the bank, or the balance at the
// start of the year; Budget Buddy adds one balance adjustment for the difference (not income or spending).

import { setAccountBalance } from "../api/endpoints.js";
import { today } from "../dates.js";
import { h } from "../dom.js";
import { accountField } from "../fields.js";
import { form } from "../form.js";
import { formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty } from "../widgets.js";

const OWED_KINDS = new Set(["credit_card", "loan"]);

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
        ["start", "The start of this year (your January statement's starting balance)"],
        ["date", "Another day (pick below)"],
      ] },
      { name: "date", label: "The day, if another day", type: "date" },
      { name: "balance", label: "Balance in dollars (card or loan: what you owe)", required: true, inputmode: "decimal" },
    ], "Set balance", async (v) => {
      const typed = v.balance.trim();
      // What you owe on a card or loan is stored as a negative balance.
      const owed = OWED_KINDS.has(kinds.get(v.account_id)) && !typed.startsWith("-");
      const saved = await setAccountBalance(Number(v.account_id), {
        date: chosenDate(v), balance: owed ? `-${typed}` : typed,
      });
      await reload({ balanceDone: saved.adjustment_cents
        ? `Added a balance adjustment of ${formatCents(saved.adjustment_cents)} on ${saved.date}.`
        : "It already matched. Nothing was added." });
    }),
    done ? h("p", { class: "ok", role: "status" }, done) : null);
}
