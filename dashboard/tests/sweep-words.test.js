import { test } from "node:test";
import assert from "node:assert/strict";
import { apartText, gapQuestion, gapText, matchText } from "../js/sweep-words.js";

test("how far apart, in words", () => {
  assert.equal(apartText(0), "same day");
  assert.equal(apartText(1), "1 day after it");
  assert.equal(apartText(-3), "3 days before it");
});

test("a possible match reads as one line", () => {
  const m = { kind: "trade", date: "2026-10-02", description: "FAKECO", amount_cents: -50000, exact: true, gap_cents: 0,
    days_apart: 7 };
  assert.equal(matchText(m), "2026-10-02 · Trade · FAKECO · -$500.00 (same amount, sweep 7 days after it)");
  const long = { ...m, kind: "dividend", description: "X".repeat(60), exact: false, gap_cents: 5, days_apart: 0 };
  assert.match(matchText(long), /^2026-10-02 · Dividend · X{23}… · .*\(\$0\.05 off, sweep same day\)$/);
  assert.match(gapQuestion(long), /\$0\.05 apart.*that \$0\.05 won't be counted anywhere/);
});

test("an account's gap, or nothing when it adds up", () => {
  assert.equal(gapText({ payments: 3, with_sweep: 3, free_sweeps: 0 }), null);
  assert.equal(gapText({ payments: 3, with_sweep: 2, free_sweeps: 1 }),
    "1 dividend or trade without a sweep, 1 sweep line not linked");
  assert.equal(gapText({ payments: 4, with_sweep: 2, free_sweeps: 0 }), "2 dividends or trades without a sweep");
});
