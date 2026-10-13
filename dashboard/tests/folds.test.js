// Folded cards: their names, remembering them (even when storage is blocked or holds junk), and defaults.

import assert from "node:assert/strict";
import test from "node:test";

import { foldId, isOpen, loadFolds, saveFold } from "../js/folds.js";

function fakeStorage(start = {}) {
  const items = new Map(Object.entries(start));
  return { getItem: (k) => (items.has(k) ? items.get(k) : null), setItem: (k, v) => items.set(k, v) };
}

const blocked = {
  getItem() { throw new Error("blocked"); },
  setItem() { throw new Error("blocked"); },
};

test("a card's name ignores numbers, case and punctuation", () => {
  assert.equal(foldId("Dividends in 2026"), "dividends-in");
  assert.equal(foldId("Dividends in 2027"), "dividends-in");
  assert.equal(foldId("Needs, wants and savings"), "needs-wants-and-savings");
  assert.equal(foldId("Match your bank's balance"), "match-your-bank-s-balance");
});

test("a folded card stays folded, and an opened one open", () => {
  const storage = fakeStorage();
  saveFold(storage, "add-a-transaction", true);
  saveFold(storage, "the-last-months", false);
  assert.deepEqual(loadFolds(storage), { "add-a-transaction": true, "the-last-months": false });
});

test("a card nobody changed uses its own default", () => {
  const folds = { "the-last-months": false };
  assert.equal(isOpen(folds, "the-last-months", true), false);
  assert.equal(isOpen(folds, "add-a-transaction", false), false);
  assert.equal(isOpen(folds, "accounts", true), true);
});

test("nothing saved, junk, or blocked storage means every card uses its default", () => {
  assert.deepEqual(loadFolds(null), {});
  assert.deepEqual(loadFolds(fakeStorage()), {});
  assert.deepEqual(loadFolds(blocked), {});
  for (const junk of ["not json", "[true]", "42", "null"]) {
    assert.deepEqual(loadFolds(fakeStorage({ "budget-buddy-folds": junk })), {});
  }
  const mixed = fakeStorage({ "budget-buddy-folds": '{"a": true, "b": "yes", "c": false}' });
  assert.deepEqual(loadFolds(mixed), { a: true, c: false });
});

test("saving never throws, even when storage is blocked or missing", () => {
  assert.doesNotThrow(() => saveFold(blocked, "a", true));
  assert.doesNotThrow(() => saveFold(null, "a", true));
});
