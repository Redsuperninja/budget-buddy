// Transactions: filter by account and month, change a category, add one by hand.

import {
  createTransaction, listAccounts, listCategories, listTransactions, updateTransaction,
} from "../api/endpoints.js";
import { currentMonth, monthRange, today } from "../dates.js";
import { fill, h, showError } from "../dom.js";
import { accountField, categoryField, idOrNull, pickOptions } from "../fields.js";
import { form, saveWithNote } from "../form.js";
import { card, empty, select, table } from "../widgets.js";
import { centsOrThrow, formatCents } from "../money.js";

export async function render(root) {
  const [accounts, categories] = await Promise.all([
    listAccounts(), listCategories(),
  ]);
  const list = h("div", {});
  const accountFilter = select(pickOptions(accounts, "All accounts"));
  const monthFilter = h("input", { type: "month", value: currentMonth() });
  const accountNames = new Map(accounts.map((a) => [a.id, a.name]));

  const categoryPicker = (t) => {
    const picker = select(pickOptions(categories, "(no category)"),
      { value: t.category_id || "", "aria-label": "Category" });
    const note = h("span", { class: "muted" });
    picker.addEventListener("change", () => saveWithNote(note, () =>
      updateTransaction(t.id, { category_id: idOrNull(picker.value) })));
    return h("span", {}, picker, note);
  };

  async function refresh() {
    const params = new URLSearchParams({ limit: "200" });
    if (accountFilter.value) params.set("account_id", accountFilter.value);
    if (monthFilter.value) {
      const { from, to } = monthRange(monthFilter.value);
      params.set("date_from", from);
      params.set("date_to", to);
    }
    try {
      const page = await listTransactions(params);
      fill(list,
        page.items.length
          ? table(["Date", "What", "Account", "Amount", "Category"], page.items.map((t) =>
              [t.date, t.description, accountNames.get(t.account_id) || "", formatCents(t.amount_cents),
                categoryPicker(t)]), [3])
          : empty("No transactions for this choice."),
        page.total > page.items.length
          ? empty(`Showing ${page.items.length} of ${page.total}. Pick a month to narrow it down.`) : null);
    } catch (err) {
      showError(list, err);
    }
  }
  accountFilter.addEventListener("change", refresh);
  monthFilter.addEventListener("change", refresh);

  fill(root,
    card("Transactions",
      h("div", { class: "toolbar" }, h("label", {}, "Account", accountFilter), h("label", {}, "Month", monthFilter)),
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
