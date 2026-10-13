// Money is whole cents. These cases cover formatting and typed-in dollars.

import assert from "node:assert/strict";
import test from "node:test";

import {
  bankBalanceToCents, centsOrThrow, centsToInput, formatBalance, formatCents, inAndOut, parseDollars,
} from "../js/money.js";

test("formatCents shows dollars with two decimals and thousands separators", () => {
  assert.equal(formatCents(0), "$0.00");
  assert.equal(formatCents(5), "$0.05");
  assert.equal(formatCents(1250), "$12.50");
  assert.equal(formatCents(123456789), "$1,234,567.89");
  assert.equal(formatCents(-1250), "-$12.50");
  assert.equal(formatCents(-5), "-$0.05");
});

test("formatBalance says owed for negative cards and loans only", () => {
  assert.equal(formatBalance(-5000, "credit_card"), "$50.00 owed");
  assert.equal(formatBalance(-5000, "loan"), "$50.00 owed");
  assert.equal(formatBalance(-5000, "checking"), "-$50.00");
  assert.equal(formatBalance(5000, "credit_card"), "$50.00");
});

test("centsToInput gives a plain number for a text box", () => {
  assert.equal(centsToInput(25000), "250.00");
  assert.equal(centsToInput(5), "0.05");
});

test("parseDollars reads common typed amounts into integer cents", () => {
  const cases = [
    ["12", 1200], ["12.5", 1250], [".50", 50], ["12.", 1200], ["$1,234.56", 123456],
    [" 7.05 ", 705], ["-5", -500], ["0", 0], ["0.07", 7], ["19.99", 1999],
  ];
  for (const [text, cents] of cases) assert.equal(parseDollars(text), cents, text);
});

test("parseDollars refuses things that are not an exact amount", () => {
  for (const text of ["", "abc", "1.234", "1e3", "--5", "12.5.1", "1234567890123", "$", "."]) {
    assert.equal(parseDollars(text), null, text);
  }
});

test("centsOrThrow explains a bad amount in plain English", () => {
  assert.equal(centsOrThrow("3.10"), 310);
  assert.throws(() => centsOrThrow("lots"), /Please enter the amount as a number, like 12.50\./);
  assert.throws(() => centsOrThrow("x", "budget"), /Please enter the budget as a number/);
});

test("shortDollars keeps chart axes short, in whole dollars", async () => {
  const { shortDollars } = await import("../js/money.js");
  assert.equal(shortDollars(0), "$0");
  assert.equal(shortDollars(95000), "$950");
  assert.equal(shortDollars(123456), "$1.2k");
  assert.equal(shortDollars(100000), "$1k");
  assert.equal(shortDollars(-250000), "-$2.5k");
  assert.equal(shortDollars(250000000), "$2.5M");
});

test("bankBalanceToCents: cards and loans are typed as what you owe", () => {
  const cases = [
    ["1,234.56", "checking", 123456],
    [" $250 ", "checking", 25000],
    ["-20", "checking", -2000],
    ["250", "credit_card", -25000],
    ["-20", "credit_card", 2000],
    ["$1,000.00", "loan", -100000],
    ["0", "credit_card", 0],
  ];
  for (const [typed, kind, cents] of cases) assert.equal(bankBalanceToCents(typed, kind), cents, `${typed} ${kind}`);
  assert.throws(() => bankBalanceToCents("lots", "checking"), /balance as a number/);
});

test("inAndOut adds money in and money out separately, both positive", () => {
  assert.deepEqual(inAndOut([]), { in: 0, out: 0 });
  assert.deepEqual(inAndOut([260000, -150000, -11865, 0, 6000]), { in: 266000, out: 161865 });
});
