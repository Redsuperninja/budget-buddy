// Receipts: the receipt photos and details you've uploaded (from the phone), newest first, each with a small preview
// and Delete for ones that are outdated. A photo the browser can't show (like an iPhone HEIC) can be downloaded.

import { deleteReceipt, listReceipts, receiptImageUrl } from "../api/endpoints.js";
import { fill, h } from "../dom.js";
import { formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty, table } from "../widgets.js";
import { removeButton } from "./remove-button.js";

function preview(r) {
  if (!r.has_image) return h("span", { class: "muted" }, "No photo");
  const link = h("a", { href: receiptImageUrl(r.id), target: "_blank", rel: "noopener", title: "Open the photo" });
  const img = h("img", { class: "thumb", src: receiptImageUrl(r.id), alt: `Receipt from ${r.merchant}`, loading: "lazy" });
  img.addEventListener("error", () => fill(link, "Download photo"), { once: true });
  fill(link, img);
  return link;
}

export async function render(root) {
  const page = await listReceipts();
  fill(root, card("Receipts",
    empty("Receipts you saved from your phone, newest first. Click a photo to open it. Delete a receipt you no " +
      "longer need: its photo is deleted too, and a transaction it was attached to stays."),
    page.items.length
      ? table(["Photo", "Date", "Shop", "Total", "Tax deductible", ""], page.items.map((r) => [
          preview(r), r.date, r.merchant, formatCents(r.total_cents), r.tax_deductible ? "Yes" : "",
          removeButton(`Delete the receipt from ${r.merchant} on ${r.date}, and its photo?`,
            () => deleteReceipt(r.id), () => reload()),
        ]), [3])
      : empty("No receipts yet. Take a photo of one in the Budget Buddy phone app, then sync."),
    page.total > page.items.length ? empty(`Showing the newest ${page.items.length} of ${page.total}.`) : null));
}
