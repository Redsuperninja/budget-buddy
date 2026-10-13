// Chart maths across months: trimming empty months, small trend lines, which days to compare, spending changes.

import assert from "node:assert/strict";
import test from "node:test";

import { comparedWith, dayOfMonth, fromFirstActivity, hasMoney, sparkPoints, spendingChanges } from "../js/charts/months.js";

const month = (m, income = 0, spending = 0, saved = 0) =>
  ({ month: m, income_cents: income, spending_cents: spending, saved_cents: saved });

test("the trend starts at the first month with anything in it", () => {
  const months = [month("2026-01"), month("2026-02"), month("2026-03", 0, 0, 500), month("2026-04"), month("2026-05", 9)];
  assert.deepEqual(fromFirstActivity(months).map((m) => m.month), ["2026-03", "2026-04", "2026-05"]);
  assert.equal(fromFirstActivity([month("2026-01", 1)]).length, 1);
  const empty = [month("2026-01"), month("2026-02")];
  assert.deepEqual(fromFirstActivity(empty), empty);
});

test("small trend lines put the highest value at the top", () => {
  assert.equal(sparkPoints([0, 50, 100], 100, 20), "0.0,20.0 50.0,10.0 100.0,0.0");
  assert.equal(sparkPoints([5, 5], 10, 20), "0.0,20.0 10.0,20.0");
  assert.equal(sparkPoints([7], 30, 20), "0.0,20.0 30,20.0");
  assert.equal(sparkPoints([-100, 100], 10, 10), "0.0,10.0 10.0,0.0");
});

test("this month so far is compared with the same days of last month", () => {
  assert.deepEqual(comparedWith("2026-10", "2026-10-13"),
    { previous: "2026-09", through: "2026-10-13", previousThrough: "2026-09-13" });
  // March 30 against February, which has only 28 days.
  assert.deepEqual(comparedWith("2026-03", "2026-03-30"),
    { previous: "2026-02", through: "2026-03-30", previousThrough: "2026-02-28" });
  assert.equal(comparedWith("2024-03", "2024-03-30").previousThrough, "2024-02-29");
  assert.deepEqual(comparedWith("2026-01", "2026-01-05"),
    { previous: "2025-12", through: "2026-01-05", previousThrough: "2025-12-05" });
});

test("a past month is compared whole", () => {
  assert.deepEqual(comparedWith("2026-01", "2026-10-13"), { previous: "2025-12", through: null, previousThrough: null });
});

// Shaped like the monthly summary's category rows (CategoryTotal), which are keyed by category_id.
const cat = (category_id, name, group, actual) => ({ category_id, name, group, actual_cents: actual });

test("spending changes: needs and wants only, biggest first, unchanged left out", () => {
  const previous = { categories: [cat(1, "Food", "needs", 300), cat(2, "Fun", "wants", 500), cat(3, "Pay", "income", 9),
    cat(4, "Rent", "needs", 1000), cat(5, "Save", "savings", 100)] };
  const current = { categories: [cat(1, "Food", "needs", 450), cat(2, "Fun", "wants", 100), cat(3, "Pay", "income", 99),
    cat(4, "Rent", "needs", 1000), cat(5, "Save", "savings", 900), cat(6, "New", "wants", 150)] };
  assert.deepEqual(spendingChanges(current, previous), [
    { label: "Fun", cents: -400 }, { label: "Food", cents: 150 }, { label: "New", cents: 150 }]);
});

test("past the limit, the smallest changes add up into Everything else", () => {
  const current = { categories: [1, 2, 3, 4].map((n) => cat(n, `C${n}`, "wants", n * 100)) };
  const previous = { categories: [] };
  assert.deepEqual(spendingChanges(current, previous, 3),
    [{ label: "C4", cents: 400 }, { label: "C3", cents: 300 }, { label: "Everything else", cents: 300 }]);
  const cancelling = { categories: [cat(1, "A", "wants", 900), cat(2, "B", "wants", 50), cat(3, "C", "wants", -50)] };
  assert.deepEqual(spendingChanges(cancelling, previous, 2), [{ label: "A", cents: 900 }]);
});

test("days of the month read as words", () => {
  const days = ["01", "02", "03", "04", "11", "12", "13", "21", "22", "23", "30", "31"].map((d) => dayOfMonth(`2026-10-${d}`));
  assert.deepEqual(days, ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "30th", "31st"]);
});

test("a month has money in it when anything came in or went out, sorted or not", () => {
  assert.equal(hasMoney(month("2026-01")), false);
  assert.equal(hasMoney(month("2026-01", 0, 0, 1)), true);
  assert.equal(hasMoney({ income_cents: 0, spending_cents: 0, saved_cents: 0, unassigned_in_cents: 0,
    unassigned_out_cents: 250 }), true);
  assert.equal(hasMoney({ income_cents: 0, spending_cents: 0, saved_cents: 0, unassigned_in_cents: 5,
    unassigned_out_cents: 0 }), true);
});
