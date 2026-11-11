import { test } from "node:test";
import assert from "node:assert/strict";

import { buildParts, canSplit, leftToAssign, leftWords, rowCents, splitHover, splitLabel, startRows } from "../js/splits.js";
import { formatCents } from "../js/money.js";

const out = { id: 1, kind: "normal", amount_cents: -5000, transfer_pair_id: null, donation_id: null, splits: [] };
const row = (category_id, amount, note = "") => ({ category_id, amount, note });

test("dollars to cents for a row", () => {
  assert.equal(rowCents(row("1", "12.5")), 1250);
  assert.equal(rowCents(row("1", "$1,000.00")), 100000);
  assert.equal(rowCents(row("1", "0")), null);
  assert.equal(rowCents(row("1", "-3")), null);
  assert.equal(rowCents(row("1", "abc")), null);
  assert.equal(rowCents(row("1", "1.234")), null);
});

test("left to assign counts only valid rows", () => {
  assert.equal(leftToAssign(out, [row("1", "30"), row("2", "")]), 2000);
  assert.equal(leftToAssign(out, [row("1", "30"), row("2", "20")]), 0);
  assert.equal(leftToAssign(out, [row("1", "30"), row("2", "25.01")]), -501);
  assert.equal(leftToAssign({ ...out, amount_cents: 1000 }, [row("1", "3")]), 700);
  assert.equal(leftWords(0, formatCents), "All assigned");
  assert.equal(leftWords(2000, formatCents), "$20.00 left to assign");
  assert.equal(leftWords(-501, formatCents), "$5.01 too much");
});

test("parts keep the transaction's direction", () => {
  const spent = buildParts(out, [row("1", "30", " milk "), row("2", "20")]);
  assert.deepEqual(spent.parts, [
    { category_id: 1, amount_cents: -3000, note: "milk" }, { category_id: 2, amount_cents: -2000, note: null }]);
  const got = buildParts({ ...out, amount_cents: 700 }, [row("1", "3"), row("2", "4")]);
  assert.deepEqual(got.parts.map((p) => p.amount_cents), [300, 400]);
});

test("validation says what is wrong in plain English", () => {
  assert.match(buildParts(out, [row("1", "50")]).error, /2 to 20 parts/);
  assert.match(buildParts(out, Array.from({ length: 21 }, () => row("1", "1"))).error, /2 to 20 parts/);
  assert.match(buildParts(out, [row("", "30"), row("2", "20")]).error, /category for part 1/);
  assert.match(buildParts(out, [row("1", "30"), row("2", "x")]).error, /amount above zero for part 2/);
  assert.match(buildParts(out, [row("1", "30"), row("2", "10")]).error, /left to assign/);
  assert.match(buildParts(out, [row("1", "30"), row("2", "30")]).error, /more than/);
});

test("which transactions get a Split button", () => {
  assert.equal(canSplit(out), true);
  assert.equal(canSplit({ ...out, kind: "refund", amount_cents: 500 }), true);
  assert.equal(canSplit({ ...out, kind: "transfer" }), false);
  assert.equal(canSplit({ ...out, kind: "adjustment" }), false);
  assert.equal(canSplit({ ...out, transfer_pair_id: 4 }), false);
  assert.equal(canSplit({ ...out, donation_id: 4 }), false);
});

test("editing starts from the saved parts, and the list words", () => {
  const split = { ...out, splits: [{ category_id: 1, amount_cents: -3000, note: "milk" }, { category_id: 2, amount_cents: -2005, note: null }] };
  assert.deepEqual(startRows(split), [row("1", "30.00", "milk"), row("2", "20.05")]);
  assert.equal(startRows(out).length, 2);
  assert.equal(splitLabel(split), "Split (2 parts)");
  assert.equal(splitHover(split, new Map([[1, "Groceries"]]), formatCents), "Groceries $30.00 (milk); Category $20.05");
});
