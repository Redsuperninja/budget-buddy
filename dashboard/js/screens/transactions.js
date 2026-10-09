// Transactions: filter by account, month and how they were sorted (or show the ones with no category yet), hide
// dividends and their sweeps, change a category, mark a gift or a stock trade, add one by hand.

import {
  createTransaction, listAccounts, listCategories, listLots, listSales, listTransactions, matchTransfers,
} from "../api/endpoints.js";
import { currentMonth, monthRange, today } from "../dates.js";
import { fill, h, showError } from "../dom.js";
import { accountField, categoryField, idOrNull, pickOptions } from "../fields.js";
import { form } from "../form.js";
import { card, empty, select, table } from "../widgets.js";
import { centsOrThrow, formatCents } from "../money.js";
import { categoryPicker } from "./category-picker.js";
import { charityCell } from "./give-to-charity.js";
import { stockTradeCell, tradeLabels } from "./stock-trade-cell.js";

export async function render(root) {
  const [accounts, firstCategories] = await Promise.all([
    listAccounts(), listCategories(),
  ]);
  let categories = firstCategories;
  const list = h("div", {});
  const accountFilter = select(pickOptions(accounts, "All accounts"));
  const monthFilter = h("input", { type: "month", value: currentMonth() });
  const sortedFilter = select([["", "Any way"], ["none", "Not yet (uncategorized)"], ["rule", "Auto-sorted"],
    ["you", "Picked by you"]]);
  const hideDividends = h("input", { type: "checkbox" });
  const accountNames = new Map(accounts.map((a) => [a.id, a.name]));
  const accountKinds = new Map(accounts.map((a) => [a.id, a.kind]));

  async function refresh() {
    const params = new URLSearchParams({ limit: "200" });
    if (accountFilter.value) params.set("account_id", accountFilter.value);
    if (sortedFilter.value === "none") params.set("uncategorized", "true");
    else if (sortedFilter.value) params.set("sorted_by", sortedFilter.value);
    if (hideDividends.checked) params.set("hide_dividends", "true");
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
        page.items.length
          ? table(["Date", "What", "Account", "Amount", "Category", "Mark as"], page.items.map((t) =>
              [t.date, t.description, accountNames.get(t.account_id) || "", formatCents(t.amount_cents),
                categoryPicker(t, categories), h("span", {}, charityCell(t, refresh),
                  stockTradeCell(t, accountKinds.get(t.account_id), trades, refresh))]), [3])
          : empty(sortedFilter.value === "none" ? "Everything here has a category." : "No transactions for this choice."),
        page.total > page.items.length
          ? empty(`Showing ${page.items.length} of ${page.total}. Pick a month to narrow it down.`) : null);
    } catch (err) {
      showError(list, err);
    }
  }
  accountFilter.addEventListener("change", refresh);
  monthFilter.addEventListener("change", refresh);
  sortedFilter.addEventListener("change", refresh);
  hideDividends.addEventListener("change", refresh);

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

  fill(root,
    card("Transactions",
      h("div", { class: "toolbar" }, h("label", {}, "Account", accountFilter), h("label", {}, "Month", monthFilter),
        h("label", {}, "Category set", sortedFilter), h("label", {}, hideDividends, " Hide dividends and sweeps"),
        h("span", {}, findTransfers, matchNote)),
      list),
    accounts.length
      ? card("Add a transaction", form([
          accountField(accounts),
          { name: "date", label: "Date", type: "date", value: today(), required: true },
          { name: "direction", label: "Money", options: [["out", "Money out (spent)"], ["in", "Money in (received)"]] },
          { name: "amount", label: "Amount in dollars", required: true, placeholder: "12.50", inputmode: "decimal" },
          { name: "description", label: "What was it?", required: true, maxlength: 500 },
          categoryField(categories, "(none yet)"),
          { name: "kind", label: "Type",
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
