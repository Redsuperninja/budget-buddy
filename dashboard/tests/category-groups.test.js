// Categories sorted into groups, with budget totals that keep amounts and percentages apart.

import assert from "node:assert/strict";
import test from "node:test";

import { budgetLeft, budgetWords, byGroup, overBadge, overBudget } from "../js/category-groups.js";

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

test("what's left of a budget, or how far over", () => {
  assert.deepEqual(budgetLeft(21_200, 60_000), { state: "left", cents: 38_800 });
  assert.deepEqual(budgetLeft(60_000, 60_000), { state: "left", cents: 0 });
  assert.deepEqual(budgetLeft(23_450, 20_000), { state: "over", cents: 3_450 });
  assert.deepEqual(budgetLeft(-2_399, 15_000), { state: "left", cents: 15_000 }); // refunds bigger than spending
  assert.deepEqual(budgetLeft(4_000, 0), { state: "none", cents: 4_000 });
  assert.deepEqual(budgetLeft(-500, 0), { state: "none", cents: 0 });
});

test("budget words: spending left and over", () => {
  assert.deepEqual(budgetWords({ actual: 21_216, budget: 60_000 }),
    { right: "$387.84 left", below: "$212.16 spent of $600.00", alarm: false, used: 0.3536 });
  assert.deepEqual(budgetWords({ actual: 23_450, budget: 20_000 }),
    { right: "$34.50 over", below: "$234.50 spent of $200.00", alarm: true, used: 1.1725 });
  assert.deepEqual(budgetWords({ actual: 4_000, budget: 0 }),
    { right: "No budget", below: "$40.00 spent", alarm: false, used: 0 });
});

test("budget words: refunds bigger than spending use nothing", () => {
  assert.deepEqual(budgetWords({ actual: -2_399, budget: 15_000 }),
    { right: "$150.00 left", below: "$0.00 spent of $150.00", alarm: false, used: 0 });
});

test("budget words: savings are goals, never alarming, and money taken out says so", () => {
  assert.deepEqual(budgetWords({ actual: 35_000, budget: 30_000, saving: true }),
    { right: "$50.00 extra", below: "$350.00 saved of $300.00", alarm: false, used: 1 });
  assert.deepEqual(budgetWords({ actual: 0, budget: 20_000, saving: true }),
    { right: "$200.00 to go", below: "$0.00 saved of $200.00", alarm: false, used: 0 });
  assert.equal(budgetWords({ actual: -5_000, budget: 20_000, saving: true }).below, "$50.00 taken out");
});

test("budget words: a percentage budget mid-month is only so far", () => {
  const row = { actual: 40_000, budget: 30_000, percent_bp: 1_500 };
  assert.deepEqual(budgetWords(row, { provisional: true }),
    { right: "$100.00 over so far", below: "$400.00 spent of $300.00 so far", alarm: false, used: 4 / 3 });
  assert.equal(budgetWords(row).alarm, true);
  assert.deepEqual(budgetWords({ actual: 4_000, budget: 0, percent_bp: 1_500 }, { provisional: true }),
    { right: "15% of income", below: "$40.00 spent", alarm: false, used: 0 });
  assert.equal(budgetWords({ actual: 1, budget: 100 }, { provisional: true }).right, "$0.99 left"); // amounts aren't "so far"
});
