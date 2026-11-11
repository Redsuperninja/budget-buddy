// Part of the Transactions screen: split one transaction across categories. The cell shows a "Split" button (or
// "Split (3 parts)" with an Edit button) and opens an editor with a row per part and a running "left to assign" that
// must reach $0.00 before Save. Rules in splits.js; the server checks them again and its plain-English errors show here.

import { setSplits } from "../../api/endpoints.js";
import { fill, h } from "../../dom.js";
import { pickOptions } from "../../fields.js";
import { formatCents } from "../../money.js";
import { MAX_PARTS, MIN_PARTS, buildParts, canSplit, isSplit, leftToAssign, leftWords, splitHover, splitLabel, startRows } from "../../splits.js";
import { select } from "../../widgets.js";

function editor(cell, t, categories, onSaved, close) {
  const rows = startRows(t);
  const left = h("strong", { role: "status" });
  const message = h("p", { class: "error", role: "alert" });
  const list = h("div", { class: "split-rows" });
  const save = h("button", { type: "button", class: "primary" }, "Save split");
  const total = formatCents(Math.abs(t.amount_cents));

  function update() {
    const remaining = leftToAssign(t, rows);
    left.textContent = leftWords(remaining, formatCents);
    left.className = remaining === 0 ? "split-ok" : "split-left";
    save.disabled = remaining !== 0;
  }
  function draw() {
    fill(list, rows.map((row, i) => {
      const category = select(pickOptions(categories, "(pick a category)"), { value: row.category_id, "aria-label": `Category, part ${i + 1}` });
      const amount = h("input", { value: row.amount, inputmode: "decimal", size: 8, placeholder: "0.00", "aria-label": `Amount in dollars, part ${i + 1}` });
      const note = h("input", { value: row.note, maxlength: 200, placeholder: "Note (optional)", "aria-label": `Note, part ${i + 1}` });
      category.addEventListener("change", () => { row.category_id = category.value; });
      amount.addEventListener("input", () => { row.amount = amount.value; update(); });
      note.addEventListener("input", () => { row.note = note.value; });
      const remove = h("button", { type: "button", class: "plain", disabled: rows.length <= MIN_PARTS,
        "aria-label": `Remove part ${i + 1}`, onclick: () => { rows.splice(i, 1); draw(); } }, "Remove");
      return h("div", { class: "inline-form" }, category, amount, note, remove);
    }));
    update();
  }
  const add = h("button", { type: "button", class: "plain", onclick: () => {
    if (rows.length >= MAX_PARTS) { message.textContent = `A split has at most ${MAX_PARTS} parts.`; return; }
    rows.push({ category_id: "", amount: "", note: "" });
    message.textContent = "";
    draw();
  } }, "Add a part");

  async function send(parts) {
    save.disabled = true;
    try {
      await setSplits(t.id, parts);
      await onSaved();
    } catch (err) {
      message.textContent = err.message;
      update();
    }
  }
  save.addEventListener("click", () => {
    const { parts, error } = buildParts(t, rows);
    if (error) { message.textContent = error; return; }
    message.textContent = "";
    send(parts);
  });
  const undo = isSplit(t) && h("button", { type: "button", class: "plain", onclick: () => send([]) }, "Undo split");
  draw();
  fill(cell, h("div", { class: "split-editor" },
    h("p", { class: "muted" }, `Split ${total} into parts. Type each amount as a plain number; they must add up to ${total}.`),
    list, h("p", {}, left), message,
    h("div", { class: "inline-form" }, add, save, undo,
      h("button", { type: "button", class: "plain", onclick: close }, "Cancel"))));
}

// The category cell for a transaction. `plain` is the usual category dropdown, shown when it isn't split.
export function splitCell(t, categories, plain, onSaved) {
  const cell = h("div", {});
  const names = new Map(categories.map((c) => [c.id, c.name]));
  const open = () => editor(cell, t, categories, onSaved, show);
  function show() {
    if (isSplit(t)) {
      fill(cell, h("span", { class: "split-tag", title: splitHover(t, names, formatCents) }, splitLabel(t)), " ",
        !t.transfer_pair_id && h("button", { type: "button", class: "plain", onclick: open }, "Edit split"));
    } else {
      fill(cell, plain, canSplit(t) && [" ", h("button", { type: "button", class: "plain", onclick: open,
        title: "Put this transaction in several categories" }, "Split")]);
    }
  }
  show();
  return cell;
}
