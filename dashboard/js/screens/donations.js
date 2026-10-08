// Donations: the year's totals and paperwork to keep (an estimate), the gifts, and adding or removing one.
// Gifts can also come from a payment on the Transactions screen (give-to-charity.js).

import { createDonation, deleteDonation, donationSummary, listDonations } from "../api/endpoints.js";
import { thisYear, today } from "../dates.js";
import { fill, h } from "../dom.js";
import { taxYearHeader } from "../fields.js";
import { form, saveWithNote } from "../form.js";
import { card, empty, statCard, table } from "../widgets.js";
import { donationKindLabel } from "../labels.js";
import { centsOrThrow, formatCents } from "../money.js";
import { reload } from "../router.js";

function removeButton(d, year) {
  const status = h("span", { class: "muted" });
  const question = `Remove the gift to ${d.organization} of ${formatCents(d.amount_cents)}?` +
    (d.transaction_id ? " The payment stays in your transactions." : "");
  const remove = h("button", { class: "plain", type: "button", onclick: () => {
    if (!confirm(question)) return;
    saveWithNote(status, async () => {
      await deleteDonation(d.id);
      await reload({ year });
    });
  } }, "Remove");
  return h("span", {}, remove, status);
}

const typeText = (d) => donationKindLabel(d.kind) + (d.transaction_id ? " (from a payment)" : "");

export async function render(root, options) {
  const year = options.year || thisYear();
  const [page, summary] = await Promise.all([
    listDonations(year),
    donationSummary(year),
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
        ? table(["Date", "Charity", "Type", "Amount", "Paperwork to keep", ""], page.items.map((d) =>
            [d.date, d.organization, typeText(d), formatCents(d.amount_cents), paperwork(d), removeButton(d, year)]), [3])
        : empty("No donations for this year."),
      empty("Tip: to turn a payment into a gift, click Mark as gift on the Transactions page (under Money). " +
        "If a charity gave you money back, lower or remove the gift here."),
      empty(`Tax data last reviewed ${summary.tax_data_last_reviewed}.`)),
    card("Add a donation", form([
      { name: "date", label: "Date you gave it", type: "date", value: today(), required: true },
      { name: "organization", label: "Charity", required: true, maxlength: 200 },
      { name: "kind", label: "Type",
        options: [["cash", "Cash, check or card"], ["goods", "Goods (clothes, furniture...)"]] },
      { name: "amount", label: "Amount (or fair value of goods) in dollars", required: true, inputmode: "decimal" },
    ], "Add donation", async (v) => {
      await createDonation({
        date: v.date, organization: v.organization, kind: v.kind, amount_cents: centsOrThrow(v.amount),
      });
      await reload({ year });
    })));
}
