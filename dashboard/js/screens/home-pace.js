// Home: spending pace for the month: a plain sentence (pace-words.js), the chart, and a table of each day.

import { chartCard } from "../charts/chart-card.js";
import { paceChart } from "../charts/pace-chart.js";
import { h } from "../dom.js";
import { formatCents } from "../money.js";
import { paceSentence } from "../pace-words.js";
import { empty, table } from "../widgets.js";

export function paceCard(pace, summary) {
  const percentBudgets = summary.categories.some((c) => c.budget_percent_bp !== null);
  return chartCard("Spending pace", {
    chart: pace.days.length
      ? (width) => paceChart(pace, "Spending so far this month by day, against spending the budget evenly", width)
      : empty("Nothing to show yet."),
    table: table(["Day", "Spent so far"], pace.days.map((d) => [d.date, formatCents(d.spent_cents)]), [1]),
    lead: h("p", { class: "lead" }, paceSentence(pace, percentBudgets)),
  });
}
