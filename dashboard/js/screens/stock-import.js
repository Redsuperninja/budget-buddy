// Import stock purchases and sales from a CSV file: pick an account and a file, check the preview, import.

import { importStockCsv, previewStockCsv } from "../api/endpoints.js";
import { fill, h, showError } from "../dom.js";
import { pickOptions } from "../fields.js";
import { formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty, select, table } from "../widgets.js";

const KIND = { buy: "Bought", sell: "Sold" };

export function stockImportCard(accounts, year) {
  const result = h("div", {});
  const accountSelect = select(pickOptions(accounts, "(none)"));
  const fileInput = h("input", { type: "file", accept: ".csv,text/csv" });
  let bytes = null;

  const query = (extra = {}) => new URLSearchParams(
    Object.entries({ account_id: accountSelect.value, ...extra }).filter(([, v]) => v !== "")).toString();

  function importControls(p) {
    const skip = select([["false", "No, stop if any row has a problem"], ["true", "Yes, skip those rows"]]);
    const count = p.new_buys + p.new_sells;
    const button = h("button", { class: "primary", type: "button", disabled: !count, onclick: async () => {
      button.disabled = true;
      try {
        const r = await importStockCsv(query({ skip_invalid_rows: skip.value }), bytes);
        await reload({ year, imported: `Done. ${r.purchases_added} purchase(s) and ${r.sales_added} sale(s) ` +
          `added; ${r.skipped_duplicates} already there; ${r.skipped_invalid} skipped because of problems.` });
      } catch (err) {
        button.disabled = false;
        showError(result, err);
      }
    } }, `Import ${count} new row(s)`);
    return h("div", { class: "toolbar" }, h("label", {}, "Rows with problems", skip), button);
  }

  function showPreview(p) {
    const newRows = p.rows.filter((r) => r.status === "new").slice(0, 10);
    const problems = p.rows.filter((r) => r.status !== "new").slice(0, 20);
    fill(result,
      h("p", {}, `${p.total_rows} row(s) in the file: ${p.new_buys} new purchase(s), ${p.new_sells} new sale(s), ` +
        `${p.duplicate_rows} already added, ${p.invalid_rows} with problems.`),
      newRows.length ? h("div", {}, h("h3", {}, "What will be added (first rows)"),
        table(["Row", "Type", "Symbol", "Date", "Shares", "Cost or amount"], newRows.map((r) =>
          [r.row_number, KIND[r.kind], r.symbol, r.date, r.shares, formatCents(r.money_cents)]), [5])) : null,
      problems.length ? h("div", {}, h("h3", {}, "Rows with a problem or already added"),
        table(["Row", "Status", "Note"], problems.map((r) => [r.row_number, r.status, r.problem || ""]))) : null,
      importControls(p));
  }

  return card("Import from a CSV file",
    empty("Use a spreadsheet saved as CSV, or a file from your broker. The first row needs column names: " +
      "Symbol, Date, Shares (or Quantity), and Cost (or Amount: the total, including fees). To add sales too, " +
      "include a Type column that says Buy or Sell. Importing the same file twice is safe."),
    h("div", { class: "toolbar" },
      h("label", {}, "Account", accountSelect), h("label", {}, "CSV file", fileInput),
      h("button", { class: "primary", type: "button", onclick: async () => {
        try {
          if (!fileInput.files.length) throw new Error("Please choose a CSV file first.");
          bytes = await fileInput.files[0].arrayBuffer();
          showPreview(await previewStockCsv(query(), bytes));
        } catch (err) { showError(result, err); }
      } }, "Preview")),
    result);
}
