// Plain words for the Investments page's "Deposit sweeps to check" card (screens/money/sweep-check-card.js).

import { formatCents } from "./money.js";

// How far apart a sweep and a dividend or trade are. days: the sweep's date minus the other's.
export function apartText(days) {
  if (days === 0) return "same day";
  const n = Math.abs(days);
  return `${n} day${n === 1 ? "" : "s"} ${days > 0 ? "after" : "before"} it`;
}

// One possible match, for the picker: "2026-10-02 · Trade · FAKECO INC ... · -$500.00 (same amount, same day)".
export function matchText(m) {
  const amount = m.exact ? "same amount" : `${formatCents(m.gap_cents)} off`;
  const what = m.kind === "dividend" ? "Dividend" : "Trade";
  const words = m.description.length > 24 ? `${m.description.slice(0, 23)}…` : m.description;
  return `${m.date} · ${what} · ${words} · ${formatCents(m.amount_cents)} (${amount}, sweep ${apartText(m.days_apart)})`;
}

// Asked before linking amounts that aren't the same: that gap won't be counted anywhere.
export function gapQuestion(m) {
  const gap = formatCents(m.gap_cents);
  return `These amounts are ${gap} apart. Once linked, the sweep stops counting in your budget, and that ${gap} ` +
    "won't be counted anywhere. Link only if you're sure it's the same money. Link anyway?";
}

// An account's counts in a sentence when they don't add up, else null.
export function gapText(a) {
  const missing = a.payments - a.with_sweep;
  if (!missing && !a.free_sweeps) return null;
  const parts = [];
  if (missing) parts.push(`${missing} dividend${missing === 1 ? "" : "s"} or trade${missing === 1 ? "" : "s"} without a sweep`);
  if (a.free_sweeps) parts.push(`${a.free_sweeps} sweep line${a.free_sweeps === 1 ? "" : "s"} not linked`);
  return parts.join(", ");
}
