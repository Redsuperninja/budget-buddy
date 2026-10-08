// Dates: "YYYY-MM-DD" days and "YYYY-MM" months.

import assert from "node:assert/strict";
import test from "node:test";

import { currentMonth, monthRange, thisYear, today } from "../js/dates.js";

test("monthRange gives the first and last day, including leap years", () => {
  assert.deepEqual(monthRange("2026-02"), { from: "2026-02-01", to: "2026-02-28" });
  assert.deepEqual(monthRange("2028-02"), { from: "2028-02-01", to: "2028-02-29" });
  assert.deepEqual(monthRange("2026-04"), { from: "2026-04-01", to: "2026-04-30" });
  assert.deepEqual(monthRange("2026-12"), { from: "2026-12-01", to: "2026-12-31" });
});

test("today and currentMonth use the shapes the server expects", () => {
  assert.match(today(), /^\d{4}-\d{2}-\d{2}$/);
  assert.match(currentMonth(), /^\d{4}-\d{2}$/);
  assert.ok(today().startsWith(currentMonth()));
  assert.equal(Number(currentMonth().slice(0, 4)), thisYear());
});

test("monthLabel gives short chart labels, with the year on January", async () => {
  const { monthLabel } = await import("../js/dates.js");
  assert.equal(monthLabel("2026-02"), "Feb");
  assert.equal(monthLabel("2026-12"), "Dec");
  assert.equal(monthLabel("2027-01"), "Jan 2027");
});
