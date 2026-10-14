// Part of the Import files page: a brokerage activity (history) file into a brokerage, retirement or HSA account.
// Every row becomes a transaction; buys and sells also become stock trades, and dividends are filed, as it imports.

import { importActivity, previewActivity } from "../../api/endpoints.js";
import { fill, h, showError } from "../../dom.js";
import { pickOptions } from "../../fields.js";
import { formatCents } from "../../money.js";
import { card, empty, select, table } from "../../widgets.js";

const INVESTMENT_KINDS = new Set(["brokerage", "retirement", "hsa"]);

export function activityImportCard(accounts) {
  const investing = accounts.filter((a) => INVESTMENT_KINDS.has(a.kind));
  if (!investing.length) {
    return card("Import brokerage activity", empty("Add a brokerage, retirement or HSA account first, on the Accounts page."));
  }
  const result = h("div", {});
  const accountSelect = select(pickOptions(investing));
  const fileInput = h("input", { type: "file", accept: ".csv,text/csv" });
  let bytes = null;

  function showPreview(p) {
    const newRows = p.rows.filter((r) => r.status === "new").slice(0, 15);
    const problems = p.rows.filter((r) => r.status !== "new").slice(0, 20);
    const skip = select([["false", "No, stop if any row has a problem"], ["true", "Yes, skip those rows"]]);
    const button = h("button", { class: "primary", type: "button", disabled: !p.new_rows, onclick: async () => {
      button.disabled = true;
      try {
        const query = new URLSearchParams({ skip_invalid_rows: skip.value, file_name: fileInput.files[0].name });
        const r = await importActivity(accountSelect.value, query.toString(), bytes);
        fill(result, h("p", { class: "ok", role: "status" },
          `Done. ${r.imported} transaction(s) added: ${r.trades} stock trade(s) (${r.trades_linked} already on the Stocks page, now ` +
          `linked), ${r.dividends_found} dividend(s), ` +
          `${r.categorized} sorted by your rules, ${r.transfers_matched} matched as transfers; ` +
          `${r.skipped_duplicates} already there; ${r.skipped_invalid} skipped because of problems.`));
      } catch (err) {
        button.disabled = false;
        showError(result, err);
      }
    } }, `Import ${p.new_rows} new row(s)`);
    fill(result,
      h("p", {}, `${p.total_rows} row(s): ${p.new_rows} new (${p.new_trades} stock trade(s)), ` +
        `${p.duplicate_rows} already imported, ${p.skipped_rows} with no money moved (skipped), ` +
        `${p.invalid_rows} with problems.`),
      newRows.length ? table(["Row", "Date", "What", "Amount", "Stock trade"], newRows.map((r) =>
        [r.row_number, r.date, r.description, formatCents(r.amount_cents),
          r.trade ? `${r.trade}${r.trade_exists ? " (already on Stocks: linked)" : ""}` : ""]), [3]) : null,
      problems.length ? h("div", {}, h("h3", {}, "Rows with a problem or already imported"),
        table(["Row", "Status", "Note"], problems.map((r) => [r.row_number, r.status, r.problem || ""]))) : null,
      h("div", { class: "toolbar" }, h("label", {}, "Rows with problems", skip), button));
  }

  return card("Import brokerage activity",
    empty("Download the activity (or history) file from your broker as CSV. Every row becomes a transaction in the " +
      "account you pick. Buys and sells with a symbol and number of shares also become stock trades, and dividends " +
      "are filed under Dividends, so there's nothing to sort by hand. Importing the same file twice is safe."),
    h("div", { class: "toolbar" },
      h("label", {}, "Account", accountSelect), h("label", {}, "CSV file", fileInput),
      h("button", { class: "primary", type: "button", onclick: async () => {
        try {
          if (!fileInput.files.length) throw new Error("Please choose a CSV file first.");
          bytes = await fileInput.files[0].arrayBuffer();
          showPreview(await previewActivity(accountSelect.value, bytes));
        } catch (err) { showError(result, err); }
      } }, "Preview")),
    result);
}
