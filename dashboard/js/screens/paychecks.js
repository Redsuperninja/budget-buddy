// Paychecks: year totals (an estimate), the year's paychecks, pay deposits waiting for one, and adding one from a
// pay stub (started from a deposit, or blank).

import { createPaycheck, listAccounts, listPaychecks, payDeposits, paycheckSummary } from "../api/endpoints.js";
import { thisYear, today } from "../dates.js";
import { fill, h } from "../dom.js";
import { accountField, idOrNull, taxYearHeader } from "../fields.js";
import { form } from "../form.js";
import { card, empty, formCard, table } from "../widgets.js";
import { centsToInput, formatCents, parseDollars } from "../money.js";
import { reload } from "../router.js";
import { payDepositsCard } from "./pay-deposits.js";

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
  const accounts = await listAccounts();
  const [page, summary, deposits] = await Promise.all([
    listPaychecks(year),
    paycheckSummary(year),
    payDeposits(year),
  ]);
  const accountName = new Map(accounts.map((a) => [a.id, a.name]));
  const addCard = h("div", {});
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
    payDepositsCard(deposits, accountName, (d) => {
      fill(addCard, addPaycheckCard(accounts, year, d));
      addCard.scrollIntoView({ behavior: "smooth" });
    }),
    addCard);
  fill(addCard, addPaycheckCard(accounts, year, null));
}

// The pay-stub form; with a deposit, it starts from that deposit and links the paycheck to it.
function addPaycheckCard(accounts, year, deposit) {
  const start = { net_cents: deposit ? centsToInput(deposit.amount_cents) : "" };
  return (deposit ? card : formCard)(deposit ? `Fill in the paycheck paid on ${deposit.date}` : "Add a paycheck",
    empty("Copy the numbers from your pay stub. Gross minus every deduction must equal take-home pay."),
    form([
      { name: "pay_date", label: "Pay date", type: "date", value: deposit ? deposit.date : today(), required: true },
      { name: "employer", label: "Employer", required: true, maxlength: 200, value: deposit ? deposit.employer : "" },
      deposit ? null : accountField(accounts, "Paid into (optional)", "(not sure)"),
      ...PAY_FIELDS.map(([name, label]) =>
        ({ name, label: `${label} ($)`, value: start[name] || "", inputmode: "decimal" })),
    ].filter(Boolean), "Add paycheck", async (v) => {
      const json = { pay_date: v.pay_date, employer: v.employer };
      if (deposit) json.deposit_transaction_id = deposit.transaction_id;
      else json.account_id = idOrNull(v.account_id);
      for (const [name, label] of PAY_FIELDS) json[name] = stubCents(v[name], label);
      await createPaycheck(json);
      await reload({ year });
    }));
}
