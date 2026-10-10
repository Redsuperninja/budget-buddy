// Form fields several screens share: account and category pickers, the tax-year picker, and the
// small conversions from typed text to what the API wants.

import { form } from "./form.js";
import { NOT_TAX_ADVICE, everydayFirst } from "./labels.js";
import { reload } from "./router.js";
import { note } from "./widgets.js";

export const optionalText = (text) => (text.trim() === "" ? null : text.trim());
export const idOrNull = (text) => (text ? Number(text) : null);

// Items with an id and a name -> select options, optionally starting with a "none" choice.
export const pickOptions = (items, none) => [
  ...(none ? [["", none]] : []),
  ...items.map((i) => [String(i.id), i.name]),
];

// A form field for choosing an account (sent as account_id; read it with idOrNull). Everyday accounts come
// first, so it starts on checking rather than whichever account sorts first by name.
export const accountField = (accounts, label = "Account", none) =>
  ({ name: "account_id", label, options: pickOptions(everydayFirst(accounts), none) });

export const categoryField = (categories, none) =>
  ({ name: "category_id", label: "Category", options: pickOptions(categories, none) });

// "Tax year [____] Show year" plus the "Estimate, not tax advice" note (said once, even when the Home Base's
// own note already says it). Redraws the screen for the year.
export function taxYearHeader(year, detail = "") {
  const saysItAlready = /not tax advice/i.test(detail);
  return [
    form([{ name: "year", label: "Tax year", type: "number", value: year, required: true }],
      "Show year", async (v) => reload({ year: Number(v.year) })),
    note(saysItAlready ? detail : `${NOT_TAX_ADVICE} ${detail}`.trim()),
  ];
}
