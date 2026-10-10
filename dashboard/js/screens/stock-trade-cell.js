// Part of the Transactions screen: in a brokerage, retirement or HSA account, a payment can be recorded as a stock
// purchase and a deposit as a stock sale (symbol, shares, total), linked to the transaction. Linked trades say
// what they are, with Undo to delete the trade (the transaction stays); the shares and gains are on the Stocks page.

import { createLot, createSale, deleteLot, deleteSale } from "../api/endpoints.js";
import { fill, h } from "../dom.js";
import { centsOrThrow, centsToInput } from "../money.js";
import { removeButton } from "./remove-button.js";

const INVESTMENT_KINDS = new Set(["brokerage", "retirement", "hsa"]);

// Linked trades by transaction id -> { text: "Bought 2 VTI", remove } (lots and sales from the Stocks API).
export function tradeLabels(lots, sales) {
  const labels = new Map();
  for (const l of lots) {
    if (l.transaction_id) labels.set(l.transaction_id, { text: `Bought ${l.shares} ${l.symbol}`, remove: () => deleteLot(l.id) });
  }
  for (const s of sales) {
    if (s.transaction_id) labels.set(s.transaction_id, { text: `Sold ${s.shares} ${s.symbol}`, remove: () => deleteSale(s.id) });
  }
  return labels;
}

function tradeForm(cell, t, onSaved) {
  const isBuy = t.amount_cents < 0;
  const symbol = h("input", { maxlength: 16, placeholder: "VTI", size: 6, "aria-label": "Symbol" });
  const shares = h("input", { inputmode: "decimal", placeholder: "2.5", size: 6, "aria-label": "Shares" });
  const total = h("input", { value: centsToInput(Math.abs(t.amount_cents)), inputmode: "decimal", size: 8 });
  const message = h("span", { class: "error", role: "alert" });
  const save = h("button", { type: "button", class: "primary" }, "Save");
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      const common = { symbol: symbol.value, shares: shares.value.trim(), transaction_id: t.id };
      const cents = centsOrThrow(total.value);
      await (isBuy
        ? createLot({ ...common, acquired_on: t.date, cost_basis_cents: cents })
        : createSale({ ...common, sold_on: t.date, proceeds_cents: cents }));
      await onSaved();
    } catch (err) {
      message.textContent = ` ${err.message}`;
      save.disabled = false;
    }
  });
  const cancel = h("button", { type: "button", class: "plain", onclick: () => fill(cell, tradeButton(cell, t, onSaved)) },
    "Cancel");
  return h("span", { class: "inline-form" },
    h("strong", {}, isBuy ? "Stock bought" : "Stock sold"),
    h("label", {}, "Symbol", symbol), h("label", {}, "Shares", shares),
    h("label", {}, isBuy ? "Total paid with fees" : "Total received after fees", total), save, cancel, message);
}

function tradeButton(cell, t, onSaved) {
  return h("button", {
    type: "button", class: "plain", title: "Record this as a stock purchase or sale",
    onclick: () => fill(cell, tradeForm(cell, t, onSaved)),
  }, "Stock trade");
}

// accountKind: the transaction's account type; labels: from tradeLabels; onSaved redraws the list.
export function stockTradeCell(t, accountKind, labels, onSaved) {
  const trade = labels.get(t.id);
  if (trade) {
    return h("span", {}, h("a", { href: "#stocks" }, trade.text), " ",
      removeButton(`Undo "${trade.text}"? The trade is deleted from the Stocks page; the transaction stays.`,
        trade.remove, onSaved, "Undo"));
  }
  if (t.kind !== "normal" || t.transfer_pair_id || !INVESTMENT_KINDS.has(accountKind)) return "";
  const cell = h("span", {});
  fill(cell, tradeButton(cell, t, onSaved));
  return cell;
}
