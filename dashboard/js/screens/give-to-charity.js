// Part of the Transactions screen: the "Charity" column. A payment can be sorted into charity, which
// records it as a cash donation linked to that payment; a payment already sorted links to Donations.

import { createDonation } from "../api/endpoints.js";
import { fill, h } from "../dom.js";
import { centsOrThrow, centsToInput } from "../money.js";

const canGive = (t) => t.kind === "normal" && t.amount_cents < 0;

const HINT = "Date: the day you mailed the check or the card was charged; your bank may show a later day, " +
  "especially near the end of the year. Amount: if you got something back, like a dinner, enter only the part " +
  "above its value.";

// The small form that opens in the row: the charity's name, the gift's date, and how much of the payment
// was the gift. The date can differ from the bank's date (a check counts the day it was mailed).
function giveForm(cell, t, onSaved) {
  const name = h("input", { value: t.description, maxlength: 200, placeholder: "Name on the charity's receipt" });
  const date = h("input", { type: "date", value: t.date });
  const amount = h("input", { value: centsToInput(-t.amount_cents), inputmode: "decimal", size: 8 });
  const message = h("span", { class: "error", role: "alert" });
  const save = h("button", { type: "button", class: "primary" }, "Save");
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await createDonation({
        date: date.value, organization: name.value, kind: "cash",
        amount_cents: centsOrThrow(amount.value), transaction_id: t.id,
      });
      await onSaved();
    } catch (err) {
      message.textContent = ` ${err.message}`;
      save.disabled = false;
    }
  });
  const cancel = h("button", { type: "button", class: "plain", onclick: () => fill(cell, giveButton(cell, t, onSaved)) },
    "Cancel");
  return h("span", { class: "inline-form" },
    h("label", {}, "Charity", name), h("label", {}, "Date you gave it", date), h("label", {}, "Amount given", amount),
    save, cancel, h("span", { class: "muted" }, HINT), message);
}

function giveButton(cell, t, onSaved) {
  return h("button", {
    type: "button", class: "plain", title: "Record this payment as a gift to charity",
    onclick: () => fill(cell, giveForm(cell, t, onSaved)),
  }, "Mark as gift");
}

// onSaved: called after a donation is recorded (to redraw the list).
export function charityCell(t, onSaved) {
  if (t.donation_id) return h("a", { href: "#donations" }, "Gift (see Donations)");
  if (!canGive(t)) return "";
  const cell = h("span", {});
  fill(cell, giveButton(cell, t, onSaved));
  return cell;
}
