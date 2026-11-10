import { test } from "node:test";
import assert from "node:assert/strict";

import { foldAvailability } from "../js/fold-all.js";

test("with every card open only Fold all can do something", () => {
  assert.deepEqual(foldAvailability([true, true, true]), { canFold: true, canOpen: false });
});

test("with every card folded only Open all can do something", () => {
  assert.deepEqual(foldAvailability([false, false, false]), { canFold: false, canOpen: true });
});

test("with a mix both can", () => {
  assert.deepEqual(foldAvailability([true, false, true]), { canFold: true, canOpen: true });
});
