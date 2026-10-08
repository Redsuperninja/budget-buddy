// Percentages are whole basis points (1% = 100, 100% = 10000), like money is whole cents: string
// logic only, no floating-point maths.

// 1500 -> "15%", 1250 -> "12.5%", 5 -> "0.05%", null -> "".
export function formatBp(bp) {
  if (bp === null || bp === undefined) return "";
  const abs = Math.abs(bp);
  const fraction = String(abs % 100).padStart(2, "0").replace(/0+$/, "");
  return `${bp < 0 ? "-" : ""}${Math.floor(abs / 100)}${fraction ? `.${fraction}` : ""}%`;
}

// "15", "15%", "12.5 %", ".5" -> basis points, or null if it isn't a percentage (at most 2 decimals).
export function parsePercent(text) {
  const t = String(text).trim().replace(/\s*%$/, "");
  if (!/^(\d+\.?\d*|\.\d+)$/.test(t)) return null;
  const [whole, fraction = ""] = t.split(".");
  if (fraction.length > 2 || whole.length > 5) return null;
  return Number(whole || "0") * 100 + Number((fraction + "00").slice(0, 2));
}

// Whole-number percent of a budget used, rounded down; over budget always shows at least 101.
// null when there is no budget to compare with.
export function percentUsed(actualCents, budgetCents) {
  if (budgetCents <= 0) return null;
  const actual = Math.max(0, actualCents);
  const pct = Math.floor((actual * 100) / budgetCents);
  return actual > budgetCents && pct === 100 ? 101 : pct;
}
