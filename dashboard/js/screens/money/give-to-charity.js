// Part of the Transactions screen: the "Gift" column. A payment can be marked as a gift: to charity
// (a cash donation linked to the payment, filed under "Charitable giving") or a personal gift (only
// filed under "Gifts", no tax record). A payment already given to charity links to Donations.

import { createDonation, markPersonalGift } from "../../api/endpoints.js";
import { fill, h } from "../../dom.js";
import { centsOrThrow, centsToInput } from "../../money.js";
import { select } from "../../widgets.js";

const canGive = (t) => t.kind === "normal" && t.amount_cents < 0;

const HINT = "Date: the day you mailed the check or the card was charged; your bank may show a later day, " +
  "especially near the end of the year. Amount: if you got something back, like a dinner, enter only the part " +
  "above its value.";

// Run a save from a button: show what went wrong next to it, or call onSaved.
function saveButton(message, action, onSaved) {
  const save = h("button", { type: "button", class: "primary" }, "Save");
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await action();
      await onSaved();
    } catch (err) {
      message.textContent = ` ${err.message}`;
      save.disabled = false;
    }
  });
  return save;
}

// To charity: the charity's name, the gift's date (a check counts the day it was mailed, which can differ
// from the bank's date), and how much of the payment was the gift.
function charityFields(t, onSaved) {
  const name = h("input", { value: t.description, maxlength: 200, placeholder: "Name on the charity's receipt" });
  const date = h("input", { type: "date", value: t.date });
  const amount = h("input", { value: centsToInput(-t.amount_cents), inputmode: "decimal", size: 8 });
  const message = h("span", { class: "error", role: "alert" });
  const save = saveButton(message, () => createDonation({
    date: date.value, organization: name.value, kind: "cash",
    amount_cents: centsOrThrow(amount.value), transaction_id: t.id,
  }), onSaved);
  return [h("label", {}, "Charity", name), h("label", {}, "Date you gave it", date),
    h("label", {}, "Amount given", amount), save, h("span", { class: "muted" }, HINT), message];
}

function personalFields(t, onSaved) {
  const message = h("span", { class: "error", role: "alert" });
  return [h("span", { class: "muted" }, "Files this payment under Gifts. It isn't a tax record."),
    saveButton(message, () => markPersonalGift(t.id), onSaved), message];
}

function giveForm(cell, t, onSaved) {
  const kind = select([["charity", "To a charity"], ["personal", "A personal gift"]], { "aria-label": "Kind of gift" });
  const fields = h("span", { class: "inline-form" });
  const showFields = () => fill(fields,
    kind.value === "charity" ? charityFields(t, onSaved) : personalFields(t, onSaved));
  kind.addEventListener("change", showFields);
  showFields();
  const cancel = h("button", { type: "button", class: "plain", onclick: () => fill(cell, giveButton(cell, t, onSaved)) },
    "Cancel");
  return h("span", { class: "inline-form" }, h("label", {}, "Kind of gift", kind), cancel, fields);
}

function giveButton(cell, t, onSaved) {
  return h("button", {
    type: "button", class: "plain", title: "Record this payment as a gift to charity or a personal gift",
    onclick: () => fill(cell, giveForm(cell, t, onSaved)),
  }, "Mark as gift");
}

// onSaved: called after a gift is recorded (to redraw the list).
export function charityCell(t, onSaved) {
  if (t.donation_id) return h("a", { href: "#donations" }, "Gift to charity (see Donations)");
  if (!canGive(t)) return "";
  const cell = h("span", {});
  fill(cell, giveButton(cell, t, onSaved));
  return cell;
}
