// Two Home charts over the months Month by month shows (up to 12): what was left over each month (money in minus spending and saving), and
// your net worth at each month's end. Each can switch to a table.

import { chartCard } from "../../charts/chart-card.js";
import { columnChart } from "../../charts/columns.js";
import { lineChart } from "../../charts/line-chart.js";
import { monthLabel } from "../../dates.js";
import { formatCents } from "../../money.js";
import { empty, table } from "../../widgets.js";

// Money in minus spending and saving: what's left to spend or save, or (negative) how much more went out.
export const leftOver = (m) => m.income_cents - m.spending_cents - m.saved_cents;

export function leftOverChart(trend) {
  const rows = trend.months.map((m) => ({ label: monthLabel(m.month), cents: leftOver(m) }));
  const short = rows.filter((r) => r.cents < 0).length;
  return chartCard("Left over each month", {
    chart: (width) => columnChart(rows, "What was left over each month after spending and saving, or how much more went out",
      width, { up: "Left over", down: "More went out by" }),
    legendNames: ["Left over", "More went out than came in"],
    table: table(["Month", "Left over"], rows.map((r) => [r.label, formatCents(r.cents)]), [1]),
    note: empty(short
      ? `In ${short} of these months more went out than came in. Point at a column to see the amount.`
      : "Money in minus spending and saving. Point at a column to see the amount."),
  });
}

export function netWorthChart(trend) {
  const labels = trend.months.map((m) => monthLabel(m.month));
  const values = trend.months.map((m) => m.net_worth_cents);
  const first = values[0];
  const last = values[values.length - 1];
  const change = last - first;
  return chartCard("Net worth over time", {
    chart: (width) => lineChart([{ name: "Net worth", values }], labels,
      "What you have minus what you owe at the end of each month (this month so far)", width, { area: true }),
    table: table(["Month", "Net worth"], labels.map((l, i) => [l, formatCents(values[i])]), [1]),
    note: empty(`${change >= 0 ? "Up" : "Down"} ${formatCents(Math.abs(change))} since the end of ${labels[0]}. It's the sum of ` +
      "your account balances, which come from your transactions, so it doesn't follow today's stock prices."),
  });
}
