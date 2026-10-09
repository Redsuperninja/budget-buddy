// Import files (bank file): the "Which column is which?" form and the settings it starts from.

import { form } from "../form.js";

const DATE_FORMATS = ["YYYY-MM-DD", "MM/DD/YYYY", "MM/DD/YY", "DD/MM/YYYY", "DD/MM/YY", "YYYY/MM/DD",
  "MM-DD-YYYY", "DD.MM.YYYY", "YYYYMMDD", "Mon D, YYYY", "D Mon YYYY"];
const DEFAULT_MAPPING = { delimiter: ",", header_rows: 1, date_column: 0, description_column: 1,
  amount_column: 2, date_format: "YYYY-MM-DD", flip_sign: false };

// preview: the server's preview of the file. onChoose(choices) gets the column choices as query values.
export function mappingForm(preview, onChoose) {
  const m = preview.mapping || DEFAULT_MAPPING;
  const columns = (none) => [...(none ? [["", "(none)"]] : []),
    ...preview.columns.map((name, i) => [String(i), `Column ${i + 1}: ${name || "(blank)"}`])];
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
  ], "Update preview", async (v) => onChoose({
    delimiter: v.delimiter, header_rows: v.header_rows, date_column: v.date_column,
    description_column: v.description_column, date_format: v.date_format, flip_sign: v.flip_sign,
    ...(v.layout === "one"
      ? { amount_column: v.amount_column }
      : { debit_column: v.debit_column, credit_column: v.credit_column }),
  }));
}
