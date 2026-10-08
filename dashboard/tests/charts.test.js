// Chart maths: round axis steps, ranges that include zero, positions, and label spacing.

import assert from "node:assert/strict";
import test from "node:test";

import { linear, niceRange, niceStep, ticks } from "../js/charts/scale.js";

test("niceStep picks 1, 2, 2.5 or 5 times a power of ten", () => {
  assert.equal(niceStep(100, 4), 25);
  assert.equal(niceStep(1000, 4), 250);
  assert.equal(niceStep(700, 4), 200);
  assert.equal(niceStep(9, 4), 2.5);
  assert.equal(niceStep(30000, 4), 10000);
});

test("niceRange always includes zero and ends on round steps", () => {
  assert.deepEqual(niceRange(0, 95000), { lo: 0, hi: 100000, step: 25000 });
  assert.deepEqual(niceRange(-1000, 4000), { lo: -2000, hi: 4000, step: 2000 });
  assert.deepEqual(niceRange(500, 900), { lo: 0, hi: 1000, step: 250 });
  assert.deepEqual(niceRange(0, 0), { lo: 0, hi: 1, step: 0.25 }); // nothing yet: still drawable
  assert.deepEqual(niceRange(-400, -100), { lo: -400, hi: 0, step: 100 });
});

test("ticks list every step from bottom to top", () => {
  assert.deepEqual(ticks({ lo: -2000, hi: 4000, step: 2000 }), [-2000, 0, 2000, 4000]);
});

test("linear maps the range onto positions, either way up", () => {
  const range = { lo: 0, hi: 100 };
  assert.equal(linear(range, 150, 550)(50), 350);
  assert.equal(linear(range, 200, 0)(25), 150); // a y axis grows upwards
});
