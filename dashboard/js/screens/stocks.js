// Stocks: realized gains for a tax year (an estimate), dividends found in your transactions, the shares you
// bought, adding purchases and sales by hand or from a CSV file. What you hold now and its value are on the Investments page.

import { createLot, createSale, deleteLot, deleteSale, listAccounts, listLots, stockGains } from "../api/endpoints.js";
import { thisYear, today } from "../dates.js";
import { fill, h } from "../dom.js";
import { accountField, idOrNull, taxYearHeader } from "../fields.js";
import { form } from "../form.js";
import { card, empty, note, table } from "../widgets.js";
import { centsOrThrow, formatCents } from "../money.js";
import { reload } from "../router.js";
import { dividendsCard } from "./dividends-card.js";
import { removeButton } from "./remove-button.js";
import { stockImportCard } from "./stock-import.js";

const termRow = (label, t) =>
  [label, formatCents(t.proceeds_cents), formatCents(t.cost_basis_cents), formatCents(t.gain_cents)];

export async function render(root, options) {
  const year = options.year || thisYear();
  const accounts = await listAccounts();
  const accountName = new Map(accounts.map((a) => [a.id, a.name]));
  const [lots, gains, dividends] = await Promise.all([
    listLots(), stockGains(year), dividendsCard(year, accountName),
  ]);

  // Purchases and sales are entered the same way, apart from the date and money labels.
  const tradeForm = ({ dateName, dateLabel, moneyName, moneyLabel, submitLabel, save, moneyKey, moneyWhat }) =>
    form([
      { name: "symbol", label: "Symbol", required: true, maxlength: 16, placeholder: "VTI" },
      { name: dateName, label: dateLabel, type: "date", value: today(), required: true },
      { name: "shares", label: "Number of shares", required: true, inputmode: "decimal", placeholder: "2.5" },
      { name: moneyName, label: `${moneyLabel} in dollars`, required: true, inputmode: "decimal" },
      accountField(accounts, "Account (optional; retirement and HSA sales aren't taxed)", "(none)"),
    ], submitLabel, async (v) => {
      await save({
        symbol: v.symbol, [dateName]: v[dateName], shares: v.shares.trim(),
        [moneyKey]: centsOrThrow(v[moneyName], moneyWhat), account_id: idOrNull(v.account_id),
      });
      await reload({ year });
    });

  fill(root,
    options.imported ? h("p", { class: "ok", role: "status" }, options.imported) : null,
    card("Stock gains",
      taxYearHeader(year, gains.note),
      table(["Held", "Sold for", "Cost", "Gain or loss"], [
        termRow("One year or less (short term)", gains.short_term),
        termRow("More than a year (long term)", gains.long_term),
        ["Total", "", "", formatCents(gains.total_gain_cents)]], [1, 2, 3]),
      gains.possible_wash_sale_count
        ? note(`${gains.possible_wash_sale_count} sale(s) may be wash sales. See the note above.`) : null,
      h("h3", {}, `Sales in ${year}`),
      gains.sales.length
        ? table(["Date", "Symbol", "Shares", "Sold for", "Gain or loss", "Flag", ""], gains.sales.map((s) =>
            [s.sold_on, s.symbol, s.shares, formatCents(s.proceeds_cents), formatCents(s.gain_cents),
              s.possible_wash_sale ? "Possible wash sale" : "",
              removeButton(`Delete this sale of ${s.shares} ${s.symbol}?`, () => deleteSale(s.id), () => reload({ year }))]),
          [3, 4])
        : empty("No sales in this year.")),
    dividends,
    card("Shares you bought", lots.length
      ? table(["Symbol", "Account", "Bought", "Shares", "Still held", "Cost", ""], lots.map((l) =>
          [l.symbol, accountName.get(l.account_id) || "", l.acquired_on, l.shares, l.remaining_shares,
            formatCents(l.cost_basis_cents),
            removeButton(`Delete this purchase of ${l.shares} ${l.symbol}?`, () => deleteLot(l.id), () => reload({ year }))]),
        [5])
      : empty("No purchases entered yet.")),
    card("Add a purchase", tradeForm({
      dateName: "acquired_on", dateLabel: "Date bought", moneyName: "cost_basis",
      moneyLabel: "Total cost including fees", submitLabel: "Add purchase", save: createLot,
      moneyKey: "cost_basis_cents", moneyWhat: "cost" })),
    card("Add a sale", tradeForm({
      dateName: "sold_on", dateLabel: "Date sold", moneyName: "proceeds",
      moneyLabel: "Total received after fees", submitLabel: "Add sale", save: createSale,
      moneyKey: "proceeds_cents", moneyWhat: "amount received" })),
    stockImportCard(accounts, year));
}
