// Tax summary: the year's pay, donations, stock gains and other deductions in one place, a CSV
// download, printing (or saving as PDF), and adding other deductions.

import { createDeduction, deleteDeduction, listDeductions, taxExportUrl, taxSummary } from "../api/endpoints.js";
import { thisYear } from "../dates.js";
import { fill, h } from "../dom.js";
import { optionalText, taxYearHeader } from "../fields.js";
import { form, saveWithNote } from "../form.js";
import { DEDUCTION_KINDS, deductionKindLabel } from "../labels.js";
import { centsOrThrow, formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty, note, table } from "../widgets.js";

const lineTable = (lines) => table(["", "Amount"], lines.map((l) => [l.label, formatCents(l.amount_cents)]), [1]);

const STATUS_LABELS = [["single", "Single"], ["married_filing_jointly", "Married filing jointly"],
  ["married_filing_separately", "Married filing separately"], ["head_of_household", "Head of household"]];

function standardDeduction(amounts) {
  if (!amounts) return empty("Budget Buddy doesn't have this year's standard deduction yet.");
  return h("div", {},
    empty("For comparison, the basic standard deduction this year (more if you're 65 or older, or blind):"),
    table(["Filing status", "Standard deduction"], STATUS_LABELS.map(([code, text]) => [text, formatCents(amounts[code])]), [1]));
}

function actions(year) {
  return h("p", { class: "no-print" },
    h("a", { class: "button", href: taxExportUrl(year), download: "" }, "Download as a spreadsheet (CSV)"), " ",
    h("button", { class: "plain", type: "button", onclick: () => window.print() }, "Print or save as PDF"));
}

function deductionRow(d, year) {
  const status = h("span", { class: "muted" });
  const remove = h("button", { class: "plain", type: "button", onclick: () => saveWithNote(status, async () => {
    await deleteDeduction(d.id);
    await reload({ year });
  }) }, "Remove");
  return [d.date || "", deductionKindLabel(d.kind), d.description || "", formatCents(d.amount_cents), h("span", {}, remove, status)];
}

export async function render(root, options) {
  const year = options.year || thisYear();
  const [s, items] = await Promise.all([taxSummary(year), listDeductions(year)]);
  fill(root,
    card(`Tax summary for ${s.tax_year}`,
      taxYearHeader(year, s.disclaimer),
      actions(year),
      h("h3", {}, `Pay (${s.paycheck_count} paycheck(s))`), lineTable(s.pay),
      h("h3", {}, `Donations (${s.donation_count} gift(s))`), lineTable(s.donations),
      h("h3", {}, `Stock sales (${s.stock_sale_count})`), lineTable(s.stocks),
      s.possible_wash_sale_count
        ? note(`${s.possible_wash_sale_count} sale(s) may be wash sales, so their loss may not count yet. See the Stocks page.`)
        : null,
      h("h3", {}, "Other deductions"),
      s.deductions.length
        ? table(["Kind", "Items", "Total", "Where it usually goes"], s.deductions.map((d) =>
            [d.label, d.count, formatCents(d.amount_cents), d.where_text]), [1, 2])
        : empty("None recorded for this year."),
      empty("Different kinds follow different rules, so they aren't added together."),
      standardDeduction(s.standard_deduction_cents)),
    card("Other deductions this year",
      items.length
        ? table(["Date", "Kind", "Description", "Amount", ""], items.map((d) => deductionRow(d, year)), [3])
        : empty("None yet."),
      form([
        { name: "kind", label: "Kind", options: DEDUCTION_KINDS },
        { name: "amount", label: "Amount in dollars", required: true, inputmode: "decimal" },
        { name: "date", label: "Date (optional)", type: "date" },
        { name: "description", label: "Description (optional)", maxlength: 200, placeholder: "Dentist" },
      ], "Add deduction", async (v) => {
        await createDeduction({
          tax_year: year, kind: v.kind, amount_cents: centsOrThrow(v.amount),
          date: v.date || null, description: optionalText(v.description),
        });
        await reload({ year });
      })),
  );
}
