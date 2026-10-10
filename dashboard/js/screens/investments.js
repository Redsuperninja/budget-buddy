// Investments: what you hold in each account (shares, cost, value at live or typed-in prices) and this year's
// retirement and HSA contributions against the limits, and positions from your broker's file (positions-card.js). Buying and selling are on the Stocks page; live prices
// are in live-prices.js (refreshed when this page opens and on Refresh, if turned on).

import { listAccounts, retirementLimits, setStockPrice, stockHoldings } from "../api/endpoints.js";
import { thisYear, today } from "../dates.js";
import { fill, h } from "../dom.js";
import { taxYearHeader } from "../fields.js";
import { form } from "../form.js";
import { kindLabel, retirementTypeLabel } from "../labels.js";
import { formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty, note, table } from "../widgets.js";
import { priceText, refreshButton, refreshIfOn, settingsCard } from "./live-prices.js";
import { positionsCards } from "./positions-card.js";

const money = (cents) => (cents === null ? "no price yet" : formatCents(cents));

function accountCard(group) {
  const type = retirementTypeLabel(group.retirement_type) || (group.account_kind ? kindLabel(group.account_kind) : "");
  const kind = type ? ` (${type})` : "";
  return card(`${group.account_name}${kind}`,
    group.taxed ? null : empty("Not taxed when you sell inside this account."),
    table(["Symbol", "Shares", "Cost", "Price", "Value", "Gain or loss (not sold)"], group.holdings.map((x) => [
      x.symbol, x.shares, formatCents(x.cost_basis_cents),
      priceText(x),
      money(x.value_cents), x.unrealized_gain_cents === null ? "" : formatCents(x.unrealized_gain_cents),
    ]), [2, 3, 4, 5]),
    h("p", {}, h("strong", {}, `Total: ${money(group.value_cents)}`), ` (cost ${formatCents(group.cost_basis_cents)})`));
}

function priceForm(year) {
  return card("Type a price",
    empty("Type the latest price of one share, from your broker's website or app. It replaces the last price, " +
      "live or typed in. Use this for funds live prices don't cover."),
    form([
      { name: "symbol", label: "Symbol", required: true, maxlength: 16, placeholder: "VTI" },
      { name: "price", label: "Price of one share in dollars", required: true, inputmode: "decimal" },
      { name: "as_of", label: "Price on", type: "date", value: today(), required: true },
    ], "Save price", async (v) => {
      await setStockPrice({ symbol: v.symbol, price: v.price.trim(), as_of: v.as_of });
      await reload({ year });
    }));
}

// Over the limit: red, unless an age catch-up could cover it.
function overText(l) {
  if (!l.over_cents) return formatCents(l.left_cents);
  const over = `${formatCents(l.over_cents)} over`;
  return l.over_cents <= Math.max(0, ...l.catch_up_cents)
    ? h("span", {}, `${over}, fine if the age catch-up applies to you`)
    : h("span", { class: "bad" }, over);
}

function limitsCard(r) {
  return card(`Retirement and HSA contributions in ${r.tax_year}`,
    taxYearHeader(r.tax_year, r.note),
    table(["Account", "Put in", "Limit", "Room left", "Age catch-up (extra)"], r.limits.map((l) => [
      h("span", {}, l.name, h("br"), h("span", { class: "muted" }, l.note)),
      formatCents(l.contributed_cents), formatCents(l.limit_cents),
      overText(l),
      l.catch_up_cents.map((c, i) => `${formatCents(c)} (${l.catch_up_ages[i]})`).join(" or "),
    ]), [1, 2, 3]),
    empty(`Tax data last reviewed ${r.tax_data_last_reviewed}.`));
}

export async function render(root, options) {
  const year = options.year || thisYear();
  const { enabled, note: refreshed } = await refreshIfOn();  // prices first, so the totals below use them
  const accounts = await listAccounts();
  const [held, limits, settings, positions] = await Promise.all(
    [stockHoldings(), retirementLimits(year), settingsCard(year), positionsCards(accounts, year)]);
  fill(root,
    card("Your investments",
      note(held.note),
      refreshed ? h("p", { class: "muted", role: "status" }, refreshed) : null,
      refreshButton(year, enabled),
      h("p", {}, h("strong", {}, `All accounts: ${money(held.value_cents)}`),
        ` (cost ${formatCents(held.cost_basis_cents)})`),
      held.accounts.length ? null : empty("No shares held. Add purchases on the Stocks page (under Taxes).")),
    held.accounts.map(accountCard),
    positions,
    priceForm(year),
    settings,
    limitsCard(limits));
}
