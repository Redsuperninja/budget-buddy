// Chart maths for parts of a whole: the income split bar and balance bars.

import assert from "node:assert/strict";
import test from "node:test";

import { incomeSplit, percentOf, signedExtent } from "../js/charts/shares.js";

const parts = (needs, wants, saved) => [
  { name: "Needs", cents: needs }, { name: "Wants", cents: wants }, { name: "Saved", cents: saved },
];

test("a month with money left over: the bar is the income", () => {
  const split = incomeSplit(400_000, parts(200_000, 100_000, 60_000));
  assert.equal(split.total, 400_000);
  assert.deepEqual(split.segments.map((s) => [s.start, s.size, s.percent]), [
    [0, 0.5, 50], [0.5, 0.25, 25], [0.75, 0.15, 15],
  ]);
  assert.equal(split.leftover, 40_000);
  assert.equal(split.over, false);
});

test("spending more than came in: the bar grows and says by how much", () => {
  const split = incomeSplit(100_000, parts(100_000, 100_000, 0));
  assert.equal(split.total, 200_000);
  assert.deepEqual(split.segments.map((s) => s.size), [0.5, 0.5, 0]);
  assert.equal(split.leftover, -100_000);
  assert.equal(split.over, true);
});

test("no income and nothing spent still draws, without percentages", () => {
  const split = incomeSplit(0, parts(0, -500, 0)); // a refund-heavy month counts as nothing spent
  assert.equal(split.total, 0);
  assert.deepEqual(split.segments.map((s) => [s.size, s.percent, s.cents]), [[0, null, 0], [0, null, 0], [0, null, 0]]);
  assert.equal(incomeSplit(-100, parts(0, 0, 0)).total, 0);
});

test("percentOf rounds to whole percents", () => {
  assert.equal(percentOf(1, 3), 33);
  assert.equal(percentOf(2, 3), 67);
  assert.equal(percentOf(5, 0), null);
});

test("signedExtent is the biggest size either way, never zero", () => {
  assert.equal(signedExtent([500, -2000, 100]), 2000);
  assert.equal(signedExtent([]), 1);
});
