// Donations: the year's totals and paperwork to keep (an estimate), the gifts, and adding one.

import { api } from "../api.js";
import { thisYear, today } from "../dates.js";
import { card, empty, fill, form, h, statCard, table } from "../dom.js";
import { taxYearHeader } from "../forms.js";
import { donationKindLabel } from "../labels.js";
import { centsOrThrow, formatCents } from "../money.js";
import { reload } from "../router.js";

export async function render(root, options) {
  const year = options.year || thisYear();
  const [page, summary] = await Promise.all([
    api("GET", `/api/local/donations?tax_year=${year}`),
    api("GET", `/api/local/donations/summary/${year}`),
  ]);
  const proofs = new Map(summary.donations.map((d) => [d.donation_id, d.proof_needed]));
  const paperwork = (d) => (proofs.get(d.id) || []).map((p) => p.message).join(" ");

  fill(root,
    card("Donations",
      taxYearHeader(year, summary.disclaimer),
      h("div", { class: "cards" },
        statCard("Cash gifts", formatCents(summary.cash_total_cents)),
        statCard("Goods", formatCents(summary.goods_total_cents)),
        statCard("Total", formatCents(summary.total_cents))),
      summary.year_proof_needed.map((p) => h("p", { class: "note" }, p.message)),
      page.items.length
        ? table(["Date", "Charity", "Type", "Amount", "Paperwork to keep"], page.items.map((d) =>
            [d.date, d.organization, donationKindLabel(d.kind), formatCents(d.amount_cents), paperwork(d)]), [3])
        : empty("No donations for this year."),
      empty(`Tax data last reviewed ${summary.tax_data_last_reviewed}.`)),
    card("Add a donation", form([
      { name: "date", label: "Date you gave it", type: "date", value: today(), required: true },
      { name: "organization", label: "Charity", required: true, maxlength: 200 },
      { name: "kind", label: "Type",
        options: [["cash", "Cash, check or card"], ["goods", "Goods (clothes, furniture...)"]] },
      { name: "amount", label: "Amount (or fair value of goods) in dollars", required: true, inputmode: "decimal" },
    ], "Add donation", async (v) => {
      await api("POST", "/api/local/donations", { json: {
        date: v.date, organization: v.organization, kind: v.kind, amount_cents: centsOrThrow(v.amount),
      } });
      await reload({ year });
    })));
}
