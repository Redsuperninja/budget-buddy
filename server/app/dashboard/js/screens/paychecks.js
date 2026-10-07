// Paychecks: year totals (an estimate), the year's paychecks, and adding one from a pay stub.

import { api } from "../api.js";
import { thisYear, today } from "../dates.js";
import { card, empty, fill, form, h, table } from "../dom.js";
import { accountField, idOrNull, taxYearHeader } from "../forms.js";
import { formatCents, parseDollars } from "../money.js";
import { reload } from "../router.js";

const PAY_FIELDS = [
  ["gross_cents", "Gross pay"], ["federal_tax_cents", "Federal tax"], ["state_tax_cents", "State tax"],
  ["social_security_cents", "Social Security"], ["medicare_cents", "Medicare"],
  ["retirement_cents", "401(k)/403(b) before tax"], ["hsa_cents", "HSA"],
  ["health_insurance_cents", "Health insurance premiums"], ["roth_retirement_cents", "Roth 401(k)"],
  ["other_deductions_cents", "Other deductions"], ["net_cents", "Take-home (net) pay"],
];

// A blank pay-stub line counts as $0.
function stubCents(text, label) {
  if (text.trim() === "") return 0;
  const cents = parseDollars(text);
  if (cents === null || cents < 0) throw new Error(`Please enter "${label}" as a number, like 12.50.`);
  return cents;
}

export async function render(root, options) {
  const year = options.year || thisYear();
  const accounts = await api("GET", "/api/local/accounts");
  const [page, summary] = await Promise.all([
    api("GET", `/api/local/paychecks?year=${year}`),
    api("GET", `/api/local/paychecks/summary?year=${year}`),
  ]);
  const gross = summary.totals.gross_cents || 0;
  const net = summary.totals.net_cents || 0;
  const taxes = (p) => p.federal_tax_cents + p.state_tax_cents + p.social_security_cents + p.medicare_cents;

  fill(root,
    card("Paychecks",
      taxYearHeader(year, "Totals for your own records."),
      h("p", {}, `${summary.paycheck_count} paycheck(s) in ${summary.year}. Gross ${formatCents(gross)}; ` +
        `take-home ${formatCents(net)}; taxes withheld ${formatCents(summary.taxes_withheld_cents)}; ` +
        `before-tax deductions ${formatCents(summary.pre_tax_deductions_cents)}; ` +
        `after-tax deductions ${formatCents(summary.after_tax_deductions_cents)}.`),
      summary.social_security_check ? empty(summary.social_security_check.message) : null,
      summary.message ? empty(summary.message) : null,
      page.items.length
        ? table(["Date", "Employer", "Gross", "Taxes", "Take-home"], page.items.map((p) =>
            [p.pay_date, p.employer, formatCents(p.gross_cents), formatCents(taxes(p)), formatCents(p.net_cents)]),
          [2, 3, 4])
        : empty("No paychecks for this year.")),
    card("Add a paycheck",
      empty("Copy the numbers from your pay stub. Gross minus every deduction must equal take-home pay."),
      form([
        { name: "pay_date", label: "Pay date", type: "date", value: today(), required: true },
        { name: "employer", label: "Employer", required: true, maxlength: 200 },
        accountField(accounts, "Paid into (optional)", "(not sure)"),
        ...PAY_FIELDS.map(([name, label]) => ({ name, label: `${label} ($)`, value: "", inputmode: "decimal" })),
      ], "Add paycheck", async (v) => {
        const json = { pay_date: v.pay_date, employer: v.employer, account_id: idOrNull(v.account_id) };
        for (const [name, label] of PAY_FIELDS) json[name] = stubCents(v[name], label);
        await api("POST", "/api/local/paychecks", { json });
        await reload({ year });
      })));
}
