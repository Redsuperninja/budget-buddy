// Import history: every file you imported (bank files, stock trades, positions), newest first, with what it added.
// Remove undoes an import: everything it added is deleted.

import { listImports, removeImport } from "../../api/endpoints.js";
import { fill } from "../../dom.js";
import { reload } from "../../router.js";
import { card, empty, table } from "../../widgets.js";
import { removeButton } from "../../remove-button.js";

const KINDS = { bank: "Bank file", stocks: "Stock trades", activity: "Brokerage activity", positions: "Positions" };
const WHAT = { bank: "transaction(s)", stocks: "trade(s)", activity: "transaction(s)", positions: "position(s)" };

export async function render(root) {
  const imports = await listImports();
  fill(root, card("Import history",
    empty("Every file you imported, newest first. Remove one that's outdated or was a mistake: everything it " +
      "added is deleted, and transfers it was part of go back to normal. Your other data stays."),
    imports.length
      ? table(["Imported", "Kind", "Account", "File", "Added", ""], imports.map((i) => [
          i.created_at.slice(0, 16).replace("T", " "), KINDS[i.kind] || i.kind, i.account_name || "",
          i.file_name || "(no name)", `${i.rows_added} ${WHAT[i.kind] || "row(s)"}`,
          removeButton(`Remove this import and the ${i.rows_added} ${WHAT[i.kind] || "row(s)"} it added?`,
            () => removeImport(i.id), () => reload(), "Remove"),
        ]), [4])
      : empty("Nothing imported yet.")));
}
