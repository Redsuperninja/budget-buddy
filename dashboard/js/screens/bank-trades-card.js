// Part of the Investments screen: stock trades named in a bank file (like "ABBOTT LABORATORIES UNSOLICITED WE ARE
// ACTING AS PRINCIPAL ..."), each linked with the deposit sweep that moved its cash. Shows when, which company,
// bought or sold, and the amount; once you add the ticker and shares, the price per share. The ticker is offered
// again for the company's next trade. Recording uses the Stocks API, linked to the transaction.

import { createLot, createSale, dismissBankTrade, findBankTrades, listBankTrades } from "../api/endpoints.js";
import { h } from "../dom.js";
import { formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty, table } from "../widgets.js";
import { removeButton } from "./remove-button.js";

// Millionths of a share -> "10" or "2.5" (string logic, no float maths).
export function sharesText(micro) {
  const whole = Math.floor(micro / 1_000_000);
  const part = String(micro % 1_000_000).padStart(6, "0").replace(/0+$/, "");
  return part ? `${whole}.${part}` : String(whole);
}

function recordForm(t) {
  const symbol = h("input", { maxlength: 16, size: 6, value: t.suggested_symbol || "", placeholder: "ABT",
    "aria-label": `Ticker for ${t.security}` });
  const shares = h("input", { inputmode: "decimal", size: 6, placeholder: "10", "aria-label": "Shares" });
  const message = h("span", { class: "error", role: "alert" });
  const save = h("button", { type: "button", class: "primary" }, "Save");
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      const common = { symbol: symbol.value.trim(), shares: shares.value.trim(), transaction_id: t.transaction_id };
      await (t.side === "buy"
        ? createLot({ ...common, acquired_on: t.date, cost_basis_cents: t.amount_cents })
        : createSale({ ...common, sold_on: t.date, proceeds_cents: t.amount_cents }));
      await reload();
    } catch (err) {
      message.textContent = ` ${err.message}`;
      save.disabled = false;
    }
  });
  return h("span", { class: "inline-form" }, symbol, shares, save,
    removeButton(`"${t.security}" on ${t.date} isn't a stock trade? It will count like any other transaction.`,
      () => dismissBankTrade(t.id), () => reload(), "Not a trade"), message);
}

function row(t) {
  const done = t.recorded;
  return [
    t.date, t.security, t.side === "buy" ? "Bought" : "Sold", formatCents(t.amount_cents),
    done ? t.symbol : "", done ? sharesText(t.shares_micro) : "",
    done ? formatCents(t.price_cents) : "",
    done ? "" : recordForm(t),
  ];
}

export async function bankTradesCard() {
  const { items } = await listBankTrades();
  const note = h("span", { class: "muted", role: "status" });
  const find = h("button", { type: "button", class: "plain", onclick: async () => {
    try {
      const r = await findBankTrades();
      note.textContent = ` Found ${r.found} trade(s), ${r.sweeps_linked} sweep(s) linked.`;
      if (r.found || r.sweeps_linked) await reload();
    } catch (err) {
      note.textContent = ` ${err.message}`;
    }
  } }, "Find trades in my transactions");
  return card("Stock trades from your bank file",
    empty("Trades your bank file names by company, each with the deposit sweep that moved the cash. Neither counts " +
      "as spending or income. Type the ticker and number of shares once to see the price per share; the trade " +
      "then shows on the Stocks page too."),
    h("div", { class: "toolbar" }, find, note),
    items.length
      ? table(["Date", "Company", "Trade", "Amount", "Ticker", "Shares", "Price per share", ""],
          items.map(row), [3, 5, 6])
      : empty("No trades found yet. Import your brokerage account's bank file, or click Find trades."));
}
