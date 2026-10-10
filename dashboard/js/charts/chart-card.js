// A card holding a chart, an optional legend, and a "Show as table" switch, so every number in a
// chart can also be read as text (for screen readers, printing, and colors that are hard to tell apart).
// chart: an element, or (width) => SVG to draw it at the card's width (charts/fit.js).

import { h } from "../dom.js";
import { card } from "../widgets.js";
import { fitted } from "./fit.js";

// names: series names for the legend (two or more series), in the same order as the chart's colors.
export function legend(names) {
  return h("div", { class: "legend" }, names.map((name, n) =>
    h("span", { class: `series-${n + 1}` }, h("span", { class: "swatch" }), name)));
}

export function chartCard(title, { chart, table, legendNames, note, lead }) {
  const tableView = h("div", { hidden: true }, table);
  const drawn = typeof chart === "function" ? fitted(chart) : chart;
  const chartView = h("div", {}, legendNames && legendNames.length > 1 ? legend(legendNames) : null, drawn);
  const toggle = h("button", { class: "plain", type: "button", onclick: () => {
    const showTable = tableView.hidden;
    tableView.hidden = !showTable;
    chartView.hidden = showTable;
    toggle.textContent = showTable ? "Show as chart" : "Show as table";
  } }, "Show as table");
  return card(title, lead || null, h("div", { class: "toolbar no-print" }, toggle), chartView, tableView, note || null);
}
