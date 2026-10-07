// Import bank file: pick an account and a CSV, check the preview, set which column is which, import.

import { api } from "../api.js";
import { card, empty, fill, form, h, note, select, showError, table } from "../dom.js";
import { pickOptions } from "../forms.js";
import { formatCents } from "../money.js";

const DATE_FORMATS = ["YYYY-MM-DD", "MM/DD/YYYY", "MM/DD/YY", "DD/MM/YYYY", "DD/MM/YY", "YYYY/MM/DD",
  "MM-DD-YYYY", "DD.MM.YYYY", "YYYYMMDD", "Mon D, YYYY", "D Mon YYYY"];
const YES_NO = [["false", "No"], ["true", "Yes"]];
const DEFAULT_MAPPING = { delimiter: ",", header_rows: 1, date_column: 0, description_column: 1,
  amount_column: 2, date_format: "YYYY-MM-DD", flip_sign: false };

export async function render(root) {
  const accounts = await api("GET", "/api/local/accounts");
  if (!accounts.length) {
    fill(root, card("Import a bank file", empty("Add an account first, then come back here.")));
    return;
  }
  const result = h("div", {});
  const accountSelect = select(pickOptions(accounts));
  const fileInput = h("input", { type: "file", accept: ".csv,text/csv" });
  let bytes = null; // the chosen file
  let choices = {}; // column choices sent with every request (empty = let Budget Buddy guess)

  const csvPath = () => `/api/local/accounts/${accountSelect.value}/csv-import`;
  const query = (extra = {}) => new URLSearchParams(
    Object.entries({ ...choices, ...extra }).filter(([, v]) => v !== "" && v !== undefined)).toString();
  const sendCsv = (path) => api("POST", path, { body: bytes, contentType: "text/csv" });

  async function preview() {
    if (!fileInput.files.length) throw new Error("Please choose a CSV file first.");
    bytes = await fileInput.files[0].arrayBuffer();
    showPreview(await sendCsv(`${csvPath()}/preview?${query()}`));
  }

  function mappingForm(p) {
    const m = p.mapping || DEFAULT_MAPPING;
    const columns = (none) => [...(none ? [["", "(none)"]] : []),
      ...p.columns.map((name, i) => [String(i), `Column ${i + 1}: ${name || "(blank)"}`])];
    const split = m.amount_column === null || m.amount_column === undefined;
    return form([
      { name: "delimiter", label: "Columns are separated by", value: m.delimiter,
        options: [[",", "commas"], [";", "semicolons"], ["\t", "tabs"], ["|", "bars"]] },
      { name: "header_rows", label: "Rows at the top to skip (including the column names)", type: "number", value: m.header_rows },
      { name: "date_column", label: "Date", options: columns(false), value: m.date_column },
      { name: "description_column", label: "Description", options: columns(false), value: m.description_column },
      { name: "layout", label: "Amounts are in", value: split ? "split" : "one",
        options: [["one", "one column"], ["split", "separate money-out and money-in columns"]] },
      { name: "amount_column", label: "Amount", options: columns(true), value: m.amount_column ?? "" },
      { name: "debit_column", label: "Money out", options: columns(true), value: m.debit_column ?? "" },
      { name: "credit_column", label: "Money in", options: columns(true), value: m.credit_column ?? "" },
      { name: "date_format", label: "Dates look like", value: m.date_format, options: DATE_FORMATS.map((f) => [f, f]) },
      { name: "flip_sign", label: "Charges show as positive numbers (card exports)?", value: String(m.flip_sign),
        options: [["false", "No"], ["true", "Yes, flip them"]] },
    ], "Update preview", async (v) => {
      choices = {
        delimiter: v.delimiter, header_rows: v.header_rows, date_column: v.date_column,
        description_column: v.description_column, date_format: v.date_format, flip_sign: v.flip_sign,
        ...(v.layout === "one"
          ? { amount_column: v.amount_column }
          : { debit_column: v.debit_column, credit_column: v.credit_column }),
      };
      await preview();
    });
  }

  function importControls(p) {
    const remember = select(YES_NO);
    const skip = select([["false", "No, stop if any row has a problem"], ["true", "Yes, skip those rows"]]);
    const button = h("button", { class: "primary", type: "button", disabled: !p.mapping, onclick: async () => {
      button.disabled = true;
      try {
        const r = await sendCsv(`${csvPath()}?${query({ save_mapping: remember.value, skip_invalid_rows: skip.value })}`);
        fill(result, h("p", { class: "ok" }, `Done. ${r.imported} new transaction(s) added; ` +
          `${r.skipped_duplicates} already there; ${r.skipped_invalid} skipped because of problems.`));
      } catch (err) {
        showError(result, err);
      }
    } }, `Import ${p.new_rows} new row(s)`);
    return h("div", { class: "toolbar" },
      h("label", {}, "Remember these column choices for this account?", remember),
      h("label", {}, "Rows with problems", skip), button);
  }

  function showPreview(p) {
    const newRows = p.rows.filter((r) => r.status === "new").slice(0, 10);
    const problems = p.rows.filter((r) => r.status !== "new").slice(0, 20);
    fill(result,
      p.message ? note(p.message) : null,
      p.used_saved_mapping ? empty("Using the column choices you saved for this account.") : null,
      h("p", {}, `${p.total_rows} row(s) in the file: ${p.new_rows} new, ${p.duplicate_rows} already imported, ` +
        `${p.invalid_rows} with problems.`),
      p.sample.length ? h("div", {}, h("h3", {}, "First rows of your file"),
        table(p.columns.map((c) => c || "(blank)"), p.sample)) : null,
      newRows.length ? h("div", {}, h("h3", {}, "What will be imported (first rows)"),
        table(["Row", "Date", "What", "Amount"], newRows.map((r) =>
          [r.row_number, r.date, r.description, r.amount_cents === null ? "" : formatCents(r.amount_cents)]), [3])) : null,
      problems.length ? h("div", {}, h("h3", {}, "Rows with a problem or already imported"),
        table(["Row", "Status", "Note"], problems.map((r) => [r.row_number, r.status, r.problem || ""]))) : null,
      h("h3", {}, "Which column is which?"), mappingForm(p),
      h("h3", {}, "Import"), importControls(p));
  }

  fill(root, card("Import a bank file",
    empty("Download a CSV file from your bank's website, choose it here, and check the preview before anything is " +
      "saved. Importing the same file twice is safe: rows already there are skipped."),
    h("div", { class: "toolbar" },
      h("label", {}, "Account", accountSelect), h("label", {}, "CSV file", fileInput),
      h("button", { class: "primary", type: "button", onclick: async () => {
        choices = {};
        try { await preview(); } catch (err) { showError(result, err); }
      } }, "Preview")),
    result));
}
