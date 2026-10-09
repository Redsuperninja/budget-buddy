// Import bank file: pick an account and a CSV, check the preview, set which column is which, import.

import { importCsv, listAccounts, previewCsv } from "../api/endpoints.js";
import { fill, h, showError } from "../dom.js";
import { pickOptions } from "../fields.js";
import { formatCents } from "../money.js";
import { card, empty, note, select, table } from "../widgets.js";
import { mappingForm } from "./import-mapping.js";

const YES_NO = [["false", "No"], ["true", "Yes"]];

export async function render(root) {
  const accounts = await listAccounts();
  if (!accounts.length) {
    fill(root, card("Import a bank file", empty("Add an account first, then come back here.")));
    return;
  }
  const result = h("div", {});
  const accountSelect = select(pickOptions(accounts));
  const fileInput = h("input", { type: "file", accept: ".csv,text/csv" });
  let bytes = null; // the chosen file
  let choices = {}; // column choices sent with every request (empty = let Budget Buddy guess)

  const query = (extra = {}) => new URLSearchParams(
    Object.entries({ ...choices, ...extra }).filter(([, v]) => v !== "" && v !== undefined)).toString();

  async function preview() {
    if (!fileInput.files.length) throw new Error("Please choose a CSV file first.");
    bytes = await fileInput.files[0].arrayBuffer();
    showPreview(await previewCsv(accountSelect.value, query(), bytes));
  }

  function importControls(p) {
    const remember = select(YES_NO);
    const skip = select([["false", "No, stop if any row has a problem"], ["true", "Yes, skip those rows"]]);
    const button = h("button", { class: "primary", type: "button", disabled: !p.mapping, onclick: async () => {
      button.disabled = true;
      try {
        const r = await importCsv(accountSelect.value,
          query({ save_mapping: remember.value, skip_invalid_rows: skip.value }), bytes);
        fill(result, h("p", { class: "ok" }, `Done. ${r.imported} new transaction(s) added (${r.categorized} sorted by your rules, ` +
          `${r.transfers_matched} matched as transfers between your accounts); ` +
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
      h("h3", {}, "Which column is which?"), mappingForm(p, async (picked) => { choices = picked; await preview(); }),
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
