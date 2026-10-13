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

test("monthName gives the whole month name for sentences", async () => {
  const { monthName } = await import("../js/dates.js");
  assert.equal(monthName("2026-01"), "January");
  assert.equal(monthName("2026-09"), "September");
  assert.equal(monthName("2025-12"), "December");
});

test("days between dates, and in words", async () => {
  const { agoText, daysBetween } = await import("../js/dates.js");
  assert.equal(daysBetween("2026-10-13", "2026-10-13"), 0);
  assert.equal(daysBetween("2026-10-02T21:15:00", "2026-10-13"), 11);
  assert.equal(daysBetween("2026-02-28", "2026-03-01"), 1);
  assert.equal(daysBetween("2025-12-31", "2026-01-01"), 1);
  assert.equal(daysBetween("2026-03-07", "2026-03-09"), 2); // across the clocks changing
  assert.equal(agoText(0), "today");
  assert.equal(agoText(-1), "today");
  assert.equal(agoText(1), "yesterday");
  assert.equal(agoText(12), "12 days ago");
});

test("a UTC time becomes this computer's date", async () => {
  const { localDate } = await import("../js/dates.js");
  assert.equal(localDate("2026-10-13T02:30:00", 360), "2026-10-12"); // 6 hours behind UTC: still the evening before
  assert.equal(localDate("2026-10-13T02:30:00", 0), "2026-10-13");
  assert.equal(localDate("2026-10-13T22:30:00", -120), "2026-10-14"); // 2 hours ahead
  assert.match(localDate("2026-10-13T12:00:00"), /^2026-10-1[2-4]$/);
});
