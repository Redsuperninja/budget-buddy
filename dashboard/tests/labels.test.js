// Plain-English labels and the order accounts are offered in.

import assert from "node:assert/strict";
import test from "node:test";

import { everydayFirst, kindLabel } from "../js/labels.js";

test("everydayFirst puts checking, savings, card and cash first, keeping the rest in order", () => {
  const accounts = [
    { id: 1, kind: "brokerage" }, { id: 2, kind: "credit_card" }, { id: 3, kind: "hsa" },
    { id: 4, kind: "checking" }, { id: 5, kind: "savings" }, { id: 6, kind: "checking" },
  ];
  assert.deepEqual(everydayFirst(accounts).map((a) => a.id), [4, 6, 5, 2, 1, 3]);
  assert.deepEqual(accounts.map((a) => a.id), [1, 2, 3, 4, 5, 6], "the list passed in is left alone");
});

test("kindLabel names known kinds and passes unknown ones through", () => {
  assert.equal(kindLabel("credit_card"), "Credit card");
  assert.equal(kindLabel("mystery"), "mystery");
});

test("checkedLabel names what backs a trade up, and notVerified keeps the rest", async () => {
  const { checkedLabel, notVerified } = await import("../js/labels.js");
  assert.equal(checkedLabel("transaction"), "A transaction");
  assert.equal(checkedLabel("positions_file"), "Broker's positions file");
  assert.equal(checkedLabel(null), "Not verified yet");
  const records = [{ id: 1, checked_by: "transaction" }, { id: 2, checked_by: null }, { id: 3 }];
  assert.deepEqual(notVerified(records).map((r) => r.id), [2, 3]);
});

test("byFilingStatus lists every status when not set, or only the chosen one, in a fixed order", async () => {
  const { byFilingStatus, filingStatusLabel } = await import("../js/labels.js");
  const all = { head_of_household: 2_415_000, single: 1_610_000, married_filing_jointly: 3_220_000,
    married_filing_separately: 1_610_000 };
  assert.deepEqual(byFilingStatus(all), [
    ["Single", 1_610_000], ["Married filing jointly", 3_220_000],
    ["Married filing separately", 1_610_000], ["Head of household", 2_415_000],
  ]);
  assert.deepEqual(byFilingStatus({ married_filing_jointly: 3_220_000 }), [["Married filing jointly", 3_220_000]]);
  assert.deepEqual(byFilingStatus({}), []);
  assert.equal(filingStatusLabel("head_of_household"), "Head of household");
});

test("the married-filing-separately $0 note shows only when that status is listed", async () => {
  const { separateFilingNote } = await import("../js/labels.js");
  assert.match(separateFilingNote({ single: 1, married_filing_separately: 1 }), /spouse itemizes.*\$0/);
  assert.match(separateFilingNote({ married_filing_separately: 1 }), /\$0/);
  assert.equal(separateFilingNote({ married_filing_jointly: 1 }), null);
  assert.equal(separateFilingNote({}), null);
});
