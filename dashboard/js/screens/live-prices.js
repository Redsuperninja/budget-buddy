// Part of the Investments screen: live prices from Finnhub (ADR-0010). Turning them on, the key, refreshing
// when the page opens and on the Refresh button, and how each price is shown. Off until turned on.

import { priceFeed, refreshPrices, savePriceFeed } from "../api/endpoints.js";
import { h } from "../dom.js";
import { form } from "../form.js";
import { formatCents } from "../money.js";
import { reload } from "../router.js";
import { card, empty } from "../widgets.js";

// Refresh if live prices are on. Returns the settings and a short note on what happened (or null).
export async function refreshIfOn() {
  const feed = await priceFeed();
  if (!feed.enabled) return { feed, note: null };
  const r = await refreshPrices();
  const missing = r.not_found.length ? ` No price found for ${r.not_found.join(", ")}.` : "";
  return { feed, note: r.message || (r.updated.length ? `Updated ${r.updated.length} price(s).${missing}` : missing || null) };
}

// "$245.10 live, 3:42 PM" or "$245.10 on 2026-10-08 (typed in)".
export function priceText(x) {
  if (x.price_cents === null) return "";
  if (x.price_source !== "feed") return `${formatCents(x.price_cents)} on ${x.price_as_of} (typed in)`;
  const at = x.price_fetched_at ? new Date(`${x.price_fetched_at}Z`).toLocaleTimeString([], { timeStyle: "short" }) : "";
  return `${formatCents(x.price_cents)} live, ${at}`;
}

export function refreshButton(year, feed) {
  if (!feed.enabled) return null;
  return h("button", { class: "plain", type: "button", onclick: () => reload({ year }) }, "Refresh prices");
}

export function settingsCard(year, feed) {
  return card("Live prices",
    empty("Budget Buddy can get the latest prices from Finnhub (finnhub.io) when you open this page or click " +
      "Refresh prices. Only the symbols you hold, like VTI, are sent: never amounts or accounts. It needs a free " +
      "Finnhub key: sign up at finnhub.io, copy the API key from your dashboard there, and paste it here."),
    form([
      { name: "enabled", label: "Live prices", options: [["on", "On"], ["off", "Off"]], value: feed.enabled ? "on" : "off" },
      { name: "api_key", label: "Finnhub key", type: "password", maxlength: 100,
        placeholder: feed.has_key ? "Saved (type a new one to replace it)" : "Paste your key" },
    ], "Save", async (v) => {
      const body = { enabled: v.enabled === "on" };
      if (v.api_key.trim()) body.api_key = v.api_key.trim();
      await savePriceFeed(body);
      await reload({ year });
    }),
    feed.has_key ? h("p", {}, h("button", { class: "plain", type: "button", onclick: async () => {
      await savePriceFeed({ enabled: false, api_key: "" });
      await reload({ year });
    } }, "Remove my key and turn off")) : null);
}
