// Categories sorted into groups, with budget totals that keep amounts and percentages apart.

import assert from "node:assert/strict";
import test from "node:test";

import { byGroup } from "../js/category-groups.js";

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
