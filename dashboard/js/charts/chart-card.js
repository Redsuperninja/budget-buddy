// A card holding a chart, an optional legend, and a "Show as table" switch, so every number in a
// chart can also be read as text (for screen readers, printing, and colors that are hard to tell apart).

import { h } from "../dom.js";
import { card } from "../widgets.js";

// names: series names for the legend (two or more series), in the same order as the chart's colors.
export function legend(names) {
  return h("div", { class: "legend" }, names.map((name, n) =>
    h("span", { class: `series-${n + 1}` }, h("span", { class: "swatch" }), name)));
}

export function chartCard(title, { chart, table, legendNames, note }) {
  const tableView = h("div", { hidden: true }, table);
  const chartView = h("div", {}, legendNames && legendNames.length > 1 ? legend(legendNames) : null, chart);
  const toggle = h("button", { class: "plain", type: "button", onclick: () => {
    const showTable = tableView.hidden;
    tableView.hidden = !showTable;
    chartView.hidden = showTable;
    toggle.textContent = showTable ? "Show as chart" : "Show as table";
  } }, "Show as table");
  return card(title, h("div", { class: "toolbar no-print" }, toggle), chartView, tableView, note || null);
}
