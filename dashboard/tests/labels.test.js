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
