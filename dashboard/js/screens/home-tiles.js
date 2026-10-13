// The top of Home: four money tiles for the month (each with a small meter or a plain-English line), and the list
// of things that need you (transactions with no category, pay deposits to fill in, positions that don't match).

import { h } from "../dom.js";
import { formatCents } from "../money.js";
import { sparkPoints } from "../charts/months.js";
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

// A small line of the same number over the months before (at least two), drawn in the space of a line of text.
function spark(values, label) {
  if (values.length < 2) return null;
  const words = `${label}, month by month: ${values.map((v) => formatCents(v)).join(", ")}`;
  return svg("svg", { class: "spark series-1", viewBox: "0 0 100 24", preserveAspectRatio: "none", role: "img",
    "aria-label": words },
  svg("title", {}, words),
  svg("polyline", { points: sparkPoints(values, 100, 22), transform: "translate(0 1)", "vector-effect": "non-scaling-stroke" }));
}

function tile(label, value, extra, cls = "", trend = null) {
  return h("div", { class: `card tile ${cls}` }, h("div", { class: "muted" }, label), h("div", { class: "big" }, value),
    trend, extra);
}

// s: the month's summary; months: the trend, oldest first, ending with this month (fromFirstActivity).
export function monthTiles(s, months = []) {
  const line = (pick, label) => spark(months.map(pick), label);
  const leftover = s.income_cents - s.spending_cents - s.saved_cents;
  const spentShare = s.spending_budget_cents > 0 ? s.spending_cents / s.spending_budget_cents : null;
  const saveRate = percentOf(s.saved_cents, s.income_cents);
  return h("div", { class: "cards tiles" },
    tile("Money in", formatCents(s.income_cents),
      h("div", { class: "muted" }, "What everything below is measured against"), "",
      line((m) => m.income_cents, "Money in")),
    tile("Spent", formatCents(s.spending_cents), spentShare === null
      ? h("div", { class: "muted" }, "No spending budget set")
      : h("div", {}, meter(spentShare, `${Math.round(spentShare * 100)}% of the spending budget`),
          h("div", { class: "muted" }, `${Math.round(spentShare * 100)}% of ${formatCents(s.spending_budget_cents)} planned`)),
      "", line((m) => m.spending_cents, "Spent")),
    tile("Saved", formatCents(s.saved_cents), saveRate === null ? null
      : h("div", {}, meter(saveRate / 100, `${saveRate}% of income saved`),
          h("div", { class: "muted" }, `${saveRate}% of what came in`)),
      "", line((m) => m.saved_cents, "Saved")),
    tile(leftover < 0 ? "More out than in" : "Left over", formatCents(Math.abs(leftover)),
      h("div", { class: "muted" }, leftover < 0 ? "Spent and saved more than came in" : "Not spent or saved yet"),
      leftover < 0 ? "bad-tile" : "good-tile",
      line((m) => m.income_cents - m.spending_cents - m.saved_cents, "Left over")));
}

// items: [{ count, text, href, badge? }] - only the ones with something to do are shown. The badge (like "+18%")
// shows instead of the count.
export function attentionCard(items) {
  const todo = items.filter((i) => i.count > 0);
  if (!todo.length) return card(null, h("p", { class: "ok" }, "All caught up: nothing needs you right now."));
  return card("Needs your attention", h("ul", { class: "todo" }, todo.map((i) =>
    h("li", {}, h("span", { class: "count" }, i.badge || String(i.count)), " ", h("a", { href: i.href }, i.text)))));
}
