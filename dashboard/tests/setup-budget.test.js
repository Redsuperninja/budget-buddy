// The Starter budget step's pure logic: which categories can be unticked, and the take-home pay box.

import assert from "node:assert/strict";
import test from "node:test";

import { choosable, savedSummary, takeHomeFromText, toRemove } from "../js/setup-budget.js";

const cats = [
  { id: 1, name: "Groceries", group: "needs" },
  { id: 2, name: "Dining Out", group: "wants" },
  { id: 3, name: "Retirement", group: "savings" },
  { id: 4, name: "Paycheck", group: "income" },
  { id: 5, name: "Transfer", group: "transfer" },
];

test("only needs, wants and savings can be unticked", () => {
  assert.deepEqual(choosable(cats).map((g) => g.group), ["needs", "wants", "savings"]);
  assert.deepEqual(toRemove(cats, new Set([1, 4, 5])), [1]);
});

test("nothing unticked removes nothing", () => {
  assert.deepEqual(toRemove(cats, new Set()), []);
});

test("take-home pay is read like every other amount, as whole cents", () => {
  assert.deepEqual(takeHomeFromText("3200.50"), { cents: 320050 });
  assert.deepEqual(takeHomeFromText(".50"), { cents: 50 });
  assert.deepEqual(takeHomeFromText("12."), { cents: 1200 });
  assert.deepEqual(takeHomeFromText("$3,200"), { cents: 320000 });
});

test("a blank box leaves planned income alone; bad or non-positive input is an error", () => {
  assert.deepEqual(takeHomeFromText("  "), { cents: null });
  for (const bad of ["abc", "0", "-5", "1.234", "1e3"]) assert.ok(takeHomeFromText(bad).error, bad);
});

test("the summary is plain English", () => {
  assert.equal(savedSummary({ removed: 0, kept: 0, income: null }), "Nothing to change.");
  assert.equal(savedSummary({ removed: 2, kept: 1, income: 100 }),
    "Removed 2 categories. Kept 1 because it's already used by transactions, receipts or transfers. "
    + "Saved your monthly take-home pay.");
});
