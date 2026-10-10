// Two Home charts: where the month's income went (needs, wants, savings, left over), and what you have and owe
// across your accounts, with your net worth. Each can switch to a table.

import { balanceBars } from "../charts/balance-bars.js";
import { chartCard } from "../charts/chart-card.js";
import { fitted } from "../charts/fit.js";
import { incomeSplitChart } from "../charts/income-split.js";
import { incomeSplit } from "../charts/shares.js";
import { h } from "../dom.js";
import { groupLabel, kindLabel } from "../labels.js";
import { formatBalance, formatCents } from "../money.js";
import { empty, table } from "../widgets.js";

const PARTS = ["needs", "wants", "savings"];

export function incomeSplitCard(summary) {
  const byGroup = new Map(summary.groups.map((g) => [g.group, g.actual_cents]));
  const parts = PARTS.map((g) => ({ name: groupLabel(g), cents: byGroup.get(g) || 0 }));
  const split = incomeSplit(summary.income_cents, parts);
  const rows = [...split.segments.map((p) => [p.name, formatCents(p.cents), p.percent === null ? "" : `${p.percent}%`]),
    [split.over ? "More out than in" : "Left over", formatCents(Math.abs(split.leftover)), ""]];
  return chartCard("Where your income went", {
    chart: split.total > 0
      ? (width) => incomeSplitChart(summary.income_cents, parts,
        "This month's income split into needs, wants, savings and left over", width)
      : empty("Nothing came in or went out this month yet."),
    legendNames: parts.map((p) => p.name),
    table: table(["Part", "Amount", "Share of income"], rows, [1, 2]),
    note: empty(split.over
      ? "You spent and saved more than came in this month. The line on the bar is where your income ran out."
      : "Gray is what's left: not spent or saved yet. A common guide is about 50% needs, 30% wants and 20% savings."),
  });
}

export function balancesCard(accounts, investments) {
  if (!accounts.length) return chartCard("What you have and owe", { chart: empty("No accounts yet. Add one on the Accounts page."), table: null });
  const net = accounts.reduce((sum, a) => sum + a.balance_cents, 0);
  const rows = accounts.map((a) => ({ label: a.name, cents: a.balance_cents }));
  return chartCard("What you have and owe", {
    chart: h("div", {},
      h("p", {}, h("span", { class: "muted" }, "Net worth (what you have minus what you owe): "),
        h("strong", { class: `big ${net < 0 ? "bad" : ""}` }, formatCents(net))),
      fitted((width) => balanceBars(rows, "Each account's balance: money you have to the right, money owed to the left",
        width))),
    legendNames: ["Have", "Owe"],
    table: table(["Account", "Type", "Balance"],
      accounts.map((a) => [a.name, kindLabel(a.kind), formatBalance(a.balance_cents, a.kind)]), [2]),
    note: empty(investments === null
      ? "Balances come from your transactions."
      : `Balances come from your transactions. Your stocks and funds are worth ${formatCents(investments)} at your ` +
        "latest prices (see Investments)."),
  });
}
