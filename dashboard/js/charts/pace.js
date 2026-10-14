// Spending pace maths: how much of the month's budget an even pace would have used by a given day, and where the
// month ends at the pace so far. Whole cents only.

// Budget used by the end of `day` (1-based) of a `days`-day month at an even pace, rounded to the cent.
export function evenPace(budget, day, days) {
  return days > 0 ? Math.round((budget * day) / days) : 0;
}

// What the month ends at if spending keeps its pace so far, or null before any day has passed.
export function projected(spent, day, days) {
  return day > 0 ? Math.round((spent * days) / day) : null;
}
