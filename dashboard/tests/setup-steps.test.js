// When Setup is offered, and which steps show as done.

import assert from "node:assert/strict";
import test from "node:test";

import { shouldShowSetup, stepsDone } from "../js/setup-steps.js";

const first = { onThisComputer: true, hash: "", progress: { finished_at: null }, have: { accounts: 0, transactions: 0 } };

test("a first start on this computer opens Setup", () => {
  assert.equal(shouldShowSetup(first), true);
  assert.equal(shouldShowSetup({ ...first, hash: "#home" }), true);
});

test("never on a joined computer or phone", () => {
  assert.equal(shouldShowSetup({ ...first, onThisComputer: false }), false);
});

test("never once setup is finished or after Finish later", () => {
  assert.equal(shouldShowSetup({ ...first, progress: { finished_at: "2026-10-20T10:00:00Z" } }), false);
  assert.equal(shouldShowSetup({ ...first, skipped: true }), false);
});

test("never traps someone with data", () => {
  assert.equal(shouldShowSetup({ ...first, have: { accounts: 1, transactions: 0 } }), false);
  assert.equal(shouldShowSetup({ ...first, have: { accounts: 0, transactions: 3 } }), false);
});

test("a link to another page is left alone", () => {
  assert.equal(shouldShowSetup({ ...first, hash: "#transactions" }), false);
});

test("if the progress couldn't be read, Home opens", () => {
  assert.equal(shouldShowSetup({ ...first, progress: null }), false);
});

test("steps show done from the saved date and the data", () => {
  assert.deepEqual(stepsDone({ phrase_saved_at: "2026-10-20T10:00:00Z" }, { accounts: 1, transactions: 0 }),
    { phrase: true, account: true });
  assert.deepEqual(stepsDone({ phrase_saved_at: null }, { accounts: 0, transactions: 0 }),
    { phrase: false, account: false });
});
