// Categories sorted into groups, with budget totals that keep amounts and percentages apart.

import assert from "node:assert/strict";
import test from "node:test";

import { byGroup, overBadge, overBudget } from "../js/category-groups.js";

const cat = (name, group, budget_cents = 0, budget_percent_bp = null) => ({ name, group, budget_cents, budget_percent_bp });

test("groups come in a fixed order and empty ones are left out", () => {
  const groups = byGroup([cat("Pay", "income"), cat("Rent", "needs"), cat("Fun", "wants"), cat("Move", "transfer")]);
  assert.deepEqual(groups.map((g) => g.group), ["needs", "wants", "income", "transfer"]);
  assert.deepEqual(byGroup([]), []);
});

test("amounts and percentages add up separately", () => {
  // A percentage budget also reports its cents for this month; that must not be counted as an amount too.
  const [needs] = byGroup([cat("Rent", "needs", 150_000), cat("Food", "needs", 60_000),
    cat("Bills", "needs", 30_000, 1_000), cat("Car", "needs", 20_000, 550)]);
  assert.equal(needs.categories.length, 4);
  assert.equal(needs.budget_cents, 210_000);
  assert.equal(needs.budget_percent_bp, 1_550);
});

const row = (category_id, name, group, budget_cents, actual_cents, budget_percent_bp = null) =>
  ({ category_id, name, group, budget_cents, actual_cents, budget_percent_bp });

test("over budget: needs and wants past a budget, most over first", () => {
  const rows = [row(1, "Food", "needs", 60_000, 65_000), row(2, "Fun", "wants", 10_000, 23_499),
    row(3, "Rent", "needs", 150_000, 150_000), row(4, "Gifts", "wants", 0, 5_000),
    row(5, "Save", "savings", 100, 900), row(6, "Pay", "income", 0, 9_000)];
  assert.deepEqual(overBudget(rows), [
    { category_id: 2, name: "Fun", over_cents: 13_499, over_percent: 134 },
    { category_id: 1, name: "Food", over_cents: 5_000, over_percent: 8 }]);
  assert.deepEqual(overBudget([]), []);
  assert.deepEqual(overBudget([row(1, "B", "needs", 100, 200), row(2, "A", "wants", 100, 200)]).map((r) => r.name),
    ["A", "B"]);
});

test("over budget: refunds bigger than spending, and a percentage budget with no income yet, are never over", () => {
  assert.deepEqual(overBudget([row(1, "Shop", "wants", 15_000, -2_399), row(2, "Fun", "wants", 0, 4_000, 1_000)]), []);
});

test("while the month is going on income so far, percentage budgets are left out", () => {
  const rows = [row(1, "Food", "needs", 30_000, 40_000, 1_500), row(2, "Fun", "wants", 10_000, 12_000)];
  assert.deepEqual(overBudget(rows).map((r) => r.name), ["Food", "Fun"]);
  assert.deepEqual(overBudget(rows, { skipPercent: true }).map((r) => r.name), ["Fun"]);
});

test("the over-budget badge never says +0%", () => {
  assert.equal(overBadge(17), "+17%");
  assert.equal(overBadge(0), "<1%");
  const [tiny] = overBudget([row(1, "Food", "needs", 10_000, 10_001)]);
  assert.equal(overBadge(tiny.over_percent), "<1%");
});
