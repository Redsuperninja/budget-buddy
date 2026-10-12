// Transactions: search descriptions, filter by account, month, category and how they were sorted (or show the ones with no category yet), hide
// dividends and their sweeps and (by default) balance adjustments, change a category, mark a gift or a stock trade, add one by hand.
// options.sorted ("none" from Home's "needs a category" link) opens that filter across all months; options.category
// options.q (a search) and options.month open with those filters, like #transactions?category=3&month=2026-10. Finding transfers,
// hiding dividends, the "Mark as" column and the transaction type are power-user tools (All tools view).

import {
  createTransaction, listAccounts, listCategories, listLots, listSales, listTransactions, matchAgain, matchTransfers,
} from "../../api/endpoints.js";
import { currentMonth, monthRange, today } from "../../dates.js";
import { fill, h, showError } from "../../dom.js";
import { accountField, categoryField, idOrNull, pickOptions } from "../../fields.js";
import { form } from "../../form.js";
import { advanced, card, empty, formCard, select, table } from "../../widgets.js";
import { centsOrThrow, formatCents, inAndOut } from "../../money.js";
import { categoryPicker } from "./category-picker.js";
import { charityCell } from "./give-to-charity.js";
import { stockTradeCell, tradeLabels } from "./stock-trade-cell.js";

// Under a list that fits on the page: how many, and what came in and went out (balance adjustments too, when shown).
function totalsLine(items) {
  if (!items.length) return null;
  const { in: moneyIn, out } = inAndOut(items.map((t) => t.amount_cents));
  const count = items.length === 1 ? "1 transaction" : `${items.length} transactions`;
  const parts = [moneyIn ? `${formatCents(moneyIn)} in` : null, out ? `${formatCents(out)} out` : null].filter(Boolean);
  return h("p", { class: "muted" }, `${count}${parts.length ? `: ${parts.join(", ")}` : ""}.`);
}

export async function render(root, options = {}) {
  const [accounts, firstCategories] = await Promise.all([
    listAccounts(), listCategories(),
  ]);
  let categories = firstCategories;
  const list = h("div", {});
  const accountFilter = select(pickOptions(accounts, "All accounts"));
  const monthFilter = h("input", { type: "month", value: options.month || (options.sorted ? "" : currentMonth()) });
  const categoryFilter = select(pickOptions(categories, "All categories"), { value: options.category });
  const searchBox = h("input", { type: "search", placeholder: "Description contains", maxlength: 200, value: options.q });
  const sortedFilter = select([["", "Show all"], ["none", "Needs a category"], ["rule", "Sorted automatically"],
    ["you", "Sorted by you"]], { value: options.sorted });
  const hideDividends = h("input", { type: "checkbox" });
  const hideAdjustments = h("input", { type: "checkbox", checked: true });
  const accountNames = new Map(accounts.map((a) => [a.id, a.name]));
  const accountKinds = new Map(accounts.map((a) => [a.id, a.kind]));

  async function refresh() {
    const params = new URLSearchParams({ limit: "200" });
    if (accountFilter.value) params.set("account_id", accountFilter.value);
    if (categoryFilter.value) params.set("category_id", categoryFilter.value);
    if (searchBox.value.trim()) params.set("q", searchBox.value.trim());
    if (sortedFilter.value === "none") params.set("uncategorized", "true");
    else if (sortedFilter.value) params.set("sorted_by", sortedFilter.value);
    if (hideDividends.checked) params.set("hide_dividends", "true");
    if (hideAdjustments.checked) params.set("hide_adjustments", "true");
    if (monthFilter.value) {
      const { from, to } = monthRange(monthFilter.value);
      params.set("date_from", from);
      params.set("date_to", to);
    }
    try {
      // Categories again too: marking a gift can add "Charitable giving" or "Gifts".
      let page, lots, sales;
      [page, categories, lots, sales] = await Promise.all(
        [listTransactions(params), listCategories(), listLots(), listSales()]);
      const trades = tradeLabels(lots, sales);
      fill(list,
        monthFilter.value ? null : empty("Showing every month. Pick a month to narrow it down."),
        page.items.length
          ? table(["Date", "What", "Account", "Amount", "Category", "Mark as"], page.items.map((t) =>
              [t.date, t.description, accountNames.get(t.account_id) || "", formatCents(t.amount_cents),
                categoryPicker(t, categories), h("span", {}, charityCell(t, refresh),
                  stockTradeCell(t, accountKinds.get(t.account_id), trades, refresh))]), [3], [5])
          : empty(sortedFilter.value === "none" ? "Everything here has a category." : "No transactions for this choice."),
        page.total > page.items.length
          ? empty(`Showing ${page.items.length} of ${page.total}. Pick a month to narrow it down.`)
          : totalsLine(page.items));
    } catch (err) {
      showError(list, err);
    }
  }
  accountFilter.addEventListener("change", refresh);
  categoryFilter.addEventListener("change", refresh);
  // Searches as you type, once you pause.
  let typing;
  searchBox.addEventListener("input", () => { clearTimeout(typing); typing = setTimeout(refresh, 300); });
  monthFilter.addEventListener("change", refresh);
  sortedFilter.addEventListener("change", refresh);
  hideDividends.addEventListener("change", refresh);
  hideAdjustments.addEventListener("change", refresh);

  // Links card payments and moves between your accounts that weren't linked when they came in.
  const matchNote = h("span", { class: "muted", role: "status" });
  const findTransfers = h("button", { class: "plain", type: "button", onclick: async () => {
    try {
      const { matched } = await matchTransfers();
      matchNote.textContent = matched ? ` Linked ${matched} transfer(s).` : " No new transfers found.";
      await refresh();
    } catch (err) {
      matchNote.textContent = ` ${err.message}`;
    }
  } }, "Find transfers");

  // Every finder again over all transactions, so older imports get today's matching (match_again.py).
  const againNote = h("span", { class: "muted", role: "status" });
  const again = h("button", { class: "plain", type: "button", onclick: async () => {
    again.disabled = true;
    againNote.textContent = " Matching...";
    try {
      const r = await matchAgain();
      const found = r.dividends_found + r.trades_found + r.sweeps_linked + r.transfers_linked;
      againNote.textContent = found
        ? ` Done: ${r.dividends_found} new dividend(s), ${r.trades_found} new stock trade(s), ` +
          `${r.sweeps_linked} deposit sweep(s) newly linked, ${r.transfers_linked} new transfer(s).`
        : " Nothing new to match.";
      await refresh();
    } catch (err) {
      againNote.textContent = ` ${err.message}`;
    } finally {
      again.disabled = false;
    }
  } }, "Match everything again");

  fill(root,
    card("Transactions",
      h("div", { class: "toolbar" }, h("label", {}, "Search", searchBox),
        h("label", {}, "Account", accountFilter), h("label", {}, "Month", monthFilter),
        h("label", {}, "Category", categoryFilter), h("label", {}, "Show", sortedFilter),
        advanced(h("label", { class: "check" }, hideDividends, "Hide dividends, stock trades and sweeps")),
        advanced(h("label", { class: "check" }, hideAdjustments, "Hide balance adjustments")),
        advanced(h("span", {}, findTransfers, matchNote)),
        h("span", { title: "Looks through all your transactions again for dividends, stock trades, deposit sweeps " +
          "and transfers. What you decided yourself stays." }, again, againNote)),
      list),
    accounts.length
      ? formCard("Add a transaction", form([
          accountField(accounts),
          { name: "date", label: "Date", type: "date", value: today(), required: true },
          { name: "direction", label: "Money", options: [["out", "Money out (spent)"], ["in", "Money in (received)"]] },
          { name: "amount", label: "Amount in dollars", required: true, placeholder: "12.50", inputmode: "decimal" },
          { name: "description", label: "What was it?", required: true, maxlength: 500 },
          categoryField(categories, "(none yet)"),
          { name: "kind", label: "Type", advanced: true,
            options: [["normal", "Regular"], ["refund", "Refund"], ["adjustment", "Balance adjustment"]] },
        ], "Add transaction", async (v) => {
          const magnitude = Math.abs(centsOrThrow(v.amount));
          if (magnitude === 0) throw new Error("The amount can't be zero.");
          await createTransaction({
            account_id: Number(v.account_id), date: v.date, description: v.description, kind: v.kind,
            amount_cents: v.direction === "out" ? -magnitude : magnitude,
            category_id: idOrNull(v.category_id),
          });
          await refresh();
        }))
      : card("Add a transaction", empty("Add an account first.")),
  );
  await refresh();
}
