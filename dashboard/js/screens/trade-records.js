// Part of the Stocks screen: the purchases and sales you entered, each with what backs it up (a linked transaction,
// or the account's broker positions file agreeing; server services/investing/holdings_check.py), and a "Show: Not verified
// yet" filter to find the ones to check. Each can be deleted.

import { deleteLot, deleteSale } from "../api/endpoints.js";
import { fill, h } from "../dom.js";
import { checkedLabel, notVerified } from "../labels.js";
import { formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty, select, table } from "../widgets.js";
import { removeButton } from "./remove-button.js";

const checkedCell = (r) => (r.checked_by ? checkedLabel(r.checked_by) : h("span", { class: "bad" }, checkedLabel(null)));

function lotsTable(lots, accountName, year) {
  return lots.length
    ? table(["Symbol", "Account", "Bought", "Shares", "Still held", "Cost", "Checked by", ""], lots.map((l) =>
        [l.symbol, accountName.get(l.account_id) || "", l.acquired_on, l.shares, l.remaining_shares,
          formatCents(l.cost_basis_cents), checkedCell(l),
          removeButton(`Delete this purchase of ${l.shares} ${l.symbol}?`, () => deleteLot(l.id), () => reload({ year }))]),
      [5])
    : empty("Nothing to show.");
}

function salesTable(sales, accountName, year) {
  return sales.length
    ? table(["Symbol", "Account", "Sold", "Shares", "Received", "Checked by", ""], sales.map((s) =>
        [s.symbol, accountName.get(s.account_id) || "", s.sold_on, s.shares, formatCents(s.proceeds_cents),
          checkedCell(s),
          removeButton(`Delete this sale of ${s.shares} ${s.symbol}?`, () => deleteSale(s.id), () => reload({ year }))]),
      [4])
    : empty("Nothing to show.");
}

export function tradeRecordCards(lots, sales, accountName, year) {
  const show = select([["all", "All"], ["unverified", "Not verified yet"]], { "aria-label": "Show" });
  const lotsBox = h("div", {});
  const salesBox = h("div", {});
  const count = h("p", { class: "muted", role: "status" });
  function draw() {
    const pick = show.value === "unverified" ? notVerified : (records) => records;
    const waiting = notVerified(lots).length + notVerified(sales).length;
    count.textContent = waiting
      ? `${waiting} not verified yet: no linked transaction, and no broker positions file that agrees. Import your ` +
        "broker's file on the Investments page, or link the trade on the Transactions page."
      : "Every purchase and sale is backed by a transaction or your broker's positions file.";
    fill(lotsBox, lots.length ? lotsTable(pick(lots), accountName, year) : empty("No purchases entered yet."));
    fill(salesBox, sales.length ? salesTable(pick(sales), accountName, year) : empty("No sales entered yet."));
  }
  show.addEventListener("change", draw);
  draw();
  return [
    card("Shares you bought", h("div", { class: "toolbar" }, h("label", {}, "Show", show)), count, lotsBox),
    card("Sales you entered", salesBox),
  ];
}
