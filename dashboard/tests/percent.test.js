// Percentages are whole basis points. These cases cover formatting, typing and "percent used".

import assert from "node:assert/strict";
import test from "node:test";

import { formatBp, parsePercent, percentUsed } from "../js/percent.js";

test("formatBp shows only the decimals that matter", () => {
  assert.equal(formatBp(1500), "15%");
  assert.equal(formatBp(1250), "12.5%");
  assert.equal(formatBp(5), "0.05%");
  assert.equal(formatBp(10000), "100%");
  assert.equal(formatBp(-3333), "-33.33%");
  assert.equal(formatBp(null), "");
});

test("parsePercent reads typed percentages into basis points", () => {
  const cases = [["15", 1500], ["15%", 1500], ["12.5 %", 1250], [".5", 50], ["0.05", 5], ["100", 10000]];
  for (const [text, bp] of cases) assert.equal(parsePercent(text), bp, text);
  for (const bad of ["", "%", "abc", "1.234", "-5", "1e3", "123456"]) assert.equal(parsePercent(bad), null, bad);
});

test("percentUsed rounds down and never shows 100 when over", () => {
  assert.equal(percentUsed(6100, 10000), 61);
  assert.equal(percentUsed(9996, 10000), 99);
  assert.equal(percentUsed(10000, 10000), 100);
  assert.equal(percentUsed(10040, 10000), 101);
  assert.equal(percentUsed(-500, 10000), 0);
  assert.equal(percentUsed(500, 0), null);
});
