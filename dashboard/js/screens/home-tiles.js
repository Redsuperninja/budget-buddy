// The top of Home: four money tiles for the month (each with a small meter or a plain-English line), and the list
// of things that need you (transactions with no category, pay deposits to fill in, positions that don't match).

import { h } from "../dom.js";
import { formatCents } from "../money.js";
import { sparkPoints } from "../charts/months.js";
import { percentOf } from "../charts/shares.js";
import { budgetWords } from "../category-groups.js";
import { meter, ring } from "../charts/meter.js";
import { s as svg } from "../charts/svg.js";
import { card } from "../widgets.js";

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

// The Spent tile's ring and words. Any percentage spending budget makes the total only "so far" while provisional.
function spentRing(s, provisional) {
  const percent = s.categories.some((c) => (c.group === "needs" || c.group === "wants") && c.budget_percent_bp !== null);
  if (s.spending_budget_cents <= 0) {
    return h("div", { class: "muted" }, provisional && percent ? "Budgets follow your pay as it comes in"
      : "No spending budget set");
  }
  const w = budgetWords({ actual: s.spending_cents, budget: s.spending_budget_cents, percent_bp: percent ? 1 : null },
    { provisional });
  const shown = `${Math.floor(w.used * 100)}%`;
  return h("div", { class: "ring-row" },
    ring(w.used, `${shown} of the spending budget`, shown, w.alarm),
    h("div", { class: "muted" }, `of ${formatCents(s.spending_budget_cents)}`, h("br"), w.right));
}

// s: the month's summary; months: the trend, oldest first, ending with this month (fromFirstActivity);
// provisional: the month is going and percentage budgets follow the pay received so far (budgetWords).
export function monthTiles(s, months = [], provisional = false) {
  const line = (pick, label) => spark(months.map(pick), label);
  const leftover = s.income_cents - s.spending_cents - s.saved_cents;
  const saveRate = percentOf(s.saved_cents, s.income_cents);
  return h("div", { class: "cards tiles" },
    tile("Money in", formatCents(s.income_cents),
      h("div", { class: "muted" }, "What everything below is measured against"), "",
      line((m) => m.income_cents, "Money in")),
    tile("Spent", formatCents(s.spending_cents), spentRing(s, provisional), "", line((m) => m.spending_cents, "Spent")),
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
