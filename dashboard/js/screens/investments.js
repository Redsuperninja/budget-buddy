// Investments: what you hold in each account (shares, cost, value at the prices you type in) and this year's
// retirement and HSA contributions against the limits. Buying and selling are on the Stocks page.

import { retirementLimits, setStockPrice, stockHoldings } from "../api/endpoints.js";
import { thisYear, today } from "../dates.js";
import { fill, h } from "../dom.js";
import { taxYearHeader } from "../fields.js";
import { form } from "../form.js";
import { kindLabel } from "../labels.js";
import { formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty, note, table } from "../widgets.js";

const money = (cents) => (cents === null ? "no price yet" : formatCents(cents));

function accountCard(group) {
  const kind = group.account_kind ? ` (${kindLabel(group.account_kind)})` : "";
  return card(`${group.account_name}${kind}`,
    group.taxed ? null : empty("Not taxed when you sell inside this account."),
    table(["Symbol", "Shares", "Cost", "Price", "Value", "Gain or loss (not sold)"], group.holdings.map((x) => [
      x.symbol, x.shares, formatCents(x.cost_basis_cents),
      x.price_cents === null ? "" : `${formatCents(x.price_cents)} on ${x.price_as_of}`,
      money(x.value_cents), x.unrealized_gain_cents === null ? "" : formatCents(x.unrealized_gain_cents),
    ]), [2, 3, 4, 5]),
    h("p", {}, h("strong", {}, `Total: ${money(group.value_cents)}`), ` (cost ${formatCents(group.cost_basis_cents)})`));
}

function priceForm(year) {
  return card("Update a price",
    empty("Type the latest price of one share, from your broker's website or app. Budget Buddy never looks " +
      "prices up on the internet."),
    form([
      { name: "symbol", label: "Symbol", required: true, maxlength: 16, placeholder: "VTI" },
      { name: "price", label: "Price of one share in dollars", required: true, inputmode: "decimal" },
      { name: "as_of", label: "Price on", type: "date", value: today(), required: true },
    ], "Save price", async (v) => {
      await setStockPrice({ symbol: v.symbol, price: v.price.trim(), as_of: v.as_of });
      await reload({ year });
    }));
}

function limitsCard(r) {
  return card(`Retirement and HSA contributions in ${r.tax_year}`,
    taxYearHeader(r.tax_year, r.note),
    table(["Account", "Put in", "Limit", "Room left", "Age catch-up (extra)"], r.limits.map((l) => [
      h("span", {}, l.name, h("br"), h("span", { class: "muted" }, l.note)),
      formatCents(l.contributed_cents), formatCents(l.limit_cents),
      l.over_cents ? h("span", { class: "bad" }, `${formatCents(l.over_cents)} over`) : formatCents(l.left_cents),
      l.catch_up_cents.map(formatCents).join(" or "),
    ]), [1, 2, 3]),
    empty(`Tax data last reviewed ${r.tax_data_last_reviewed}.`));
}

export async function render(root, options) {
  const year = options.year || thisYear();
  const [held, limits] = await Promise.all([stockHoldings(), retirementLimits(year)]);
  fill(root,
    card("Your investments",
      note(held.note),
      h("p", {}, h("strong", {}, `All accounts: ${money(held.value_cents)}`),
        ` (cost ${formatCents(held.cost_basis_cents)})`),
      held.accounts.length ? null : empty("No shares held. Add purchases on the Stocks page (under Taxes).")),
    held.accounts.map(accountCard),
    priceForm(year),
    limitsCard(limits));
}
