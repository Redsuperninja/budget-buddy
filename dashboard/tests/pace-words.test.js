// The sentence above the Home "Spending pace" chart (js/pace-words.js).

import assert from "node:assert/strict";
import test from "node:test";

import { paceSentence } from "../js/pace-words.js";

// A 30-day month with spending of `spent` cents by the end of day `day`.
function pace(spent, day, budget = 100000, complete = false) {
  const days = Array.from({ length: day }, (_, i) => ({ date: `2026-11-${i + 1}`, spent_cents: i + 1 === day ? spent : 0 }));
  return { month: "2026-11", days_in_month: 30, budget_cents: budget, days, complete };
}

test("on track means where the month is heading, not today's gap", () => {
  assert.match(paceSentence(pace(33000, 10)), /^On track/);
  assert.match(paceSentence(pace(50000, 10)), /^Spending faster than your budget: \$500\.00 so far\. .* about \$1,500\.00, \$500\.00 over/);
  assert.match(paceSentence(pace(20000, 10)), /^Under budget so far: \$200\.00 spent\. .* about \$600\.00 .*\$400\.00 less\./);
});

test("early in the month there's no projection", () => {
  const words = paceSentence(pace(15000, 3));
  assert.match(words, /early in the month/);
  assert.doesNotMatch(words, /At this pace/);
});

test("already over, refunds, no budget, percentage budgets with no income", () => {
  assert.match(paceSentence(pace(120000, 12)), /already \$200\.00 over your \$1,000\.00 budget/);
  assert.equal(paceSentence(pace(-2000, 12)), "Refunds so far are bigger than your spending: $20.00 back.");
  assert.match(paceSentence(pace(5000, 12, 0)), /Set budgets to see your pace/);
  assert.match(paceSentence(pace(5000, 12, 0), true), /shares of income, and no income has come in yet/);
});

test("past tense only once the month is over", () => {
  assert.equal(paceSentence(pace(90000, 30, 100000, true)), "You spent $900.00 of your $1,000.00 budget.");
  assert.equal(paceSentence(pace(120000, 30, 100000, true)),
    "You spent $1,200.00, $200.00 over your $1,000.00 budget.");
  assert.match(paceSentence(pace(90000, 30, 100000, false)), /^Under budget so far/);
  assert.equal(paceSentence({ month: "2026-12", days_in_month: 31, budget_cents: 1, days: [], complete: false }),
    "This month hasn't started yet.");
});
