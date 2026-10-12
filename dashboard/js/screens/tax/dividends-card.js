// Dividends paid in a tax year, found in your bank transactions: who paid, the account, the amount, whether it's
// taxed and whether its deposit sweep was found. "Find dividends" looks through older transactions.

import { dismissDividend, findDividends, listDividends } from "../../api/endpoints.js";
import { h, showError } from "../../dom.js";
import { formatCents } from "../../money.js";
import { reload } from "../../router.js";
import { card, empty, note, table } from "../../widgets.js";

export async function dividendsCard(year, accountName) {
  const data = await listDividends(year);
  const status = h("span", { class: "muted", role: "status" });
  const find = h("button", { class: "plain", type: "button", onclick: async () => {
    try {
      const r = await findDividends();
      await reload({ year, imported: `Found ${r.found} new dividend(s) and linked ${r.sweeps_linked} deposit sweep(s).` });
    } catch (err) { showError(status, err); }
  } }, "Find dividends");
  const notDividend = (d) => h("button", { class: "plain", type: "button", onclick: async () => {
    try {
      await dismissDividend(d.id);
      await reload({ year });
    } catch (err) { showError(status, err); }
  } }, "Not a dividend");

  return card(`Dividends in ${year}`,
    note(data.note),
    h("div", { class: "toolbar" }, h("span", {}, find, status)),
    data.dividends.length
      ? table(["Paid", "Paid by", "Account", "Amount", "Taxed", "Deposit sweep", ""], data.dividends.map((d) =>
          [d.paid_on, d.payer, accountName.get(d.account_id) || "", formatCents(d.amount_cents),
            d.taxed ? "Yes" : "No (retirement or HSA)", d.sweep_transaction_id ? "Found" : "", notDividend(d)]), [3])
      : empty("No dividends found in this year. Import your bank file, or click Find dividends."),
    data.dividends.length
      ? h("p", {}, `Total ${formatCents(data.total_cents)}, of which ${formatCents(data.taxed_cents)} is taxed.`)
      : null);
}
