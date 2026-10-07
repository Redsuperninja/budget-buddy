// Stocks: realized gains for a tax year (an estimate), the shares you bought, adding purchases and sales.

import { api } from "../api.js";
import { thisYear, today } from "../dates.js";
import { card, empty, fill, form, h, note, table } from "../dom.js";
import { accountField, idOrNull, taxYearHeader } from "../forms.js";
import { centsOrThrow, formatCents } from "../money.js";
import { reload } from "../router.js";

const termRow = (label, t) =>
  [label, formatCents(t.proceeds_cents), formatCents(t.cost_basis_cents), formatCents(t.gain_cents)];

export async function render(root, options) {
  const year = options.year || thisYear();
  const accounts = await api("GET", "/api/local/accounts");
  const [lots, gains] = await Promise.all([
    api("GET", "/api/local/stocks/lots"), api("GET", `/api/local/stocks/gains/${year}`),
  ]);

  // Purchases and sales are entered the same way, apart from the date and money labels.
  const tradeForm = ({ dateName, dateLabel, moneyName, moneyLabel, submitLabel, path, moneyKey, moneyWhat }) =>
    form([
      { name: "symbol", label: "Symbol", required: true, maxlength: 16, placeholder: "VTI" },
      { name: dateName, label: dateLabel, type: "date", value: today(), required: true },
      { name: "shares", label: "Number of shares", required: true, inputmode: "decimal", placeholder: "2.5" },
      { name: moneyName, label: `${moneyLabel} in dollars`, required: true, inputmode: "decimal" },
      accountField(accounts, "Account (optional)", "(none)"),
    ], submitLabel, async (v) => {
      await api("POST", path, { json: {
        symbol: v.symbol, [dateName]: v[dateName], shares: v.shares.trim(),
        [moneyKey]: centsOrThrow(v[moneyName], moneyWhat), account_id: idOrNull(v.account_id),
      } });
      await reload({ year });
    });

  fill(root,
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
        ? table(["Date", "Symbol", "Shares", "Sold for", "Gain or loss", "Flag"], gains.sales.map((s) =>
            [s.sold_on, s.symbol, s.shares, formatCents(s.proceeds_cents), formatCents(s.gain_cents),
              s.possible_wash_sale ? "Possible wash sale" : ""]), [3, 4])
        : empty("No sales in this year.")),
    card("Shares you bought", lots.length
      ? table(["Symbol", "Bought", "Shares", "Still held", "Cost"], lots.map((l) =>
          [l.symbol, l.acquired_on, l.shares, l.remaining_shares, formatCents(l.cost_basis_cents)]), [4])
      : empty("No purchases entered yet.")),
    card("Add a purchase", tradeForm({
      dateName: "acquired_on", dateLabel: "Date bought", moneyName: "cost_basis",
      moneyLabel: "Total cost including fees", submitLabel: "Add purchase", path: "/api/local/stocks/lots",
      moneyKey: "cost_basis_cents", moneyWhat: "cost" })),
    card("Add a sale", tradeForm({
      dateName: "sold_on", dateLabel: "Date sold", moneyName: "proceeds",
      moneyLabel: "Total received after fees", submitLabel: "Add sale", path: "/api/local/stocks/sales",
      moneyKey: "proceeds_cents", moneyWhat: "amount received" })));
}
