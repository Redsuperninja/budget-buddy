// The top of Home: four money tiles for the month (each with a small meter or a plain-English line), and the list
// of things that need you (transactions with no category, pay deposits to fill in, positions that don't match).

import { h } from "../dom.js";
import { formatCents } from "../money.js";
import { percentOf } from "../charts/shares.js";
import { s as svg } from "../charts/svg.js";
import { card } from "../widgets.js";

// A thin bar showing how much of something is used (0 to 1+); over 1 shows as full and "over". An SVG, since the
// page's security rules don't allow inline styles.
function meter(used, label) {
  const share = Math.max(0, used);
  return svg("svg", { class: `meter${share > 1 ? " over" : ""}`, viewBox: "0 0 100 6", preserveAspectRatio: "none",
    role: "img", "aria-label": label },
  svg("rect", { class: "meter-track", x: 0, y: 0, width: 100, height: 6, rx: 3 }),
  share > 0 ? svg("rect", { class: "meter-fill", x: 0, y: 0, width: Math.min(1, share) * 100, height: 6, rx: 3 }) : null);
}

function tile(label, value, extra, cls = "") {
  return h("div", { class: `card tile ${cls}` }, h("div", { class: "muted" }, label), h("div", { class: "big" }, value), extra);
}

export function monthTiles(s) {
  const leftover = s.income_cents - s.spending_cents - s.saved_cents;
  const spentShare = s.spending_budget_cents > 0 ? s.spending_cents / s.spending_budget_cents : null;
  const saveRate = percentOf(s.saved_cents, s.income_cents);
  return h("div", { class: "cards tiles" },
    tile("Money in", formatCents(s.income_cents),
      h("div", { class: "muted" }, "What everything below is measured against")),
    tile("Spent", formatCents(s.spending_cents), spentShare === null
      ? h("div", { class: "muted" }, "No spending budget set")
      : h("div", {}, meter(spentShare, `${Math.round(spentShare * 100)}% of the spending budget`),
          h("div", { class: "muted" }, `${Math.round(spentShare * 100)}% of ${formatCents(s.spending_budget_cents)} planned`))),
    tile("Saved", formatCents(s.saved_cents), saveRate === null ? null
      : h("div", {}, meter(saveRate / 100, `${saveRate}% of income saved`),
          h("div", { class: "muted" }, `${saveRate}% of what came in`))),
    tile(leftover < 0 ? "More out than in" : "Left over", formatCents(Math.abs(leftover)),
      h("div", { class: "muted" }, leftover < 0 ? "Spent and saved more than came in" : "Not spent or saved yet"),
      leftover < 0 ? "bad-tile" : "good-tile"));
}

// items: [{ count, text, href }] - only the ones with something to do are shown.
export function attentionCard(items) {
  const todo = items.filter((i) => i.count > 0);
  if (!todo.length) return card(null, h("p", { class: "ok" }, "All caught up: nothing needs you right now."));
  return card("Needs your attention", h("ul", { class: "todo" }, todo.map((i) =>
    h("li", {}, h("span", { class: "count" }, String(i.count)), " ", h("a", { href: i.href }, i.text)))));
}
