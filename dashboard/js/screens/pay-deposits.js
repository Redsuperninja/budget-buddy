// Part of the Paychecks screen: pay deposits from your bank file that no paycheck explains yet. "Fill in" starts
// the Add a paycheck form with the date, employer, account and take-home pay, linked to that deposit.

import { h } from "../dom.js";
import { formatCents } from "../money.js";
import { card, empty, table } from "../widgets.js";

// onFill(deposit): show the add form for this deposit.
export function payDepositsCard(deposits, accountName, onFill) {
  return card("Pay deposits to fill in",
    deposits.length
      ? h("div", {},
          empty("These look like pay in your bank account. Fill in each one from its pay stub, so the Paychecks " +
            "page has your gross pay and taxes."),
          table(["Date", "What", "Account", "Take-home", ""], deposits.map((d) =>
            [d.date, d.description, accountName.get(d.account_id) || "", formatCents(d.amount_cents),
              h("button", { class: "plain", type: "button", onclick: () => onFill(d) }, "Fill in")]), [3]))
      : empty("No pay deposits waiting. Pay deposits from your bank files show here until a paycheck explains them."));
}
