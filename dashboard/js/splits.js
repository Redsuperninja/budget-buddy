// Splitting one transaction into parts, the pure rules (ADR-0017): which transactions can be split, typed rows ->
// parts for the server, and how much is still left to assign. Amounts are typed as positive dollars; the
// transaction's own direction (money out or in) is applied here. Whole cents only. The server checks it all again.

import { centsToInput, parseDollars } from "./money.js";

export const MIN_PARTS = 2;
export const MAX_PARTS = 20;

// The Split button is offered for these; the server refuses the rest (dividends, stock trades...) with its own words.
export const canSplit = (t) =>
  (t.kind === "normal" || t.kind === "refund") && !t.transfer_pair_id && !t.donation_id && t.amount_cents !== 0;

export const isSplit = (t) => Array.isArray(t.splits) && t.splits.length > 0;

// A row as typed: { category_id: "3", amount: "12.50", note: "" }. Cents of a row, or null if it isn't a positive amount.
export function rowCents(row) {
  const cents = parseDollars(row.amount);
  return cents !== null && cents > 0 ? cents : null;
}

// Cents of the transaction still to assign (its size minus the rows that hold an amount). Negative when over.
export const leftToAssign = (t, rows) =>
  Math.abs(t.amount_cents) - rows.reduce((sum, r) => sum + (rowCents(r) ?? 0), 0);

// Starting rows: the saved parts when editing, else the whole amount in one row and an empty one.
export function startRows(t) {
  if (isSplit(t)) {
    return t.splits.map((p) => ({
      category_id: String(p.category_id), amount: centsToInput(Math.abs(p.amount_cents)),
      note: p.note || "",
    }));
  }
  return [{ category_id: "", amount: "", note: "" }, { category_id: "", amount: "", note: "" }];
}

// { parts } ready for the PUT, or { error } in plain English (the first thing wrong).
export function buildParts(t, rows) {
  if (rows.length < MIN_PARTS || rows.length > MAX_PARTS) return { error: `A split has ${MIN_PARTS} to ${MAX_PARTS} parts.` };
  const sign = t.amount_cents < 0 ? -1 : 1;
  const parts = [];
  for (const [i, row] of rows.entries()) {
    if (!row.category_id) return { error: `Pick a category for part ${i + 1}.` };
    const cents = rowCents(row);
    if (cents === null) return { error: `Enter an amount above zero for part ${i + 1}, like 12.50.` };
    parts.push({ category_id: Number(row.category_id), amount_cents: sign * cents, note: row.note.trim() || null });
  }
  const left = leftToAssign(t, rows);
  if (left !== 0) return { error: left > 0 ? "There is still money left to assign." : "The parts add up to more than the transaction." };
  return { parts };
}

// The words next to the amount: "$3.00 left to assign", "$1.00 too much" or "All assigned".
export function leftWords(left, format) {
  if (left === 0) return "All assigned";
  return left > 0 ? `${format(left)} left to assign` : `${format(-left)} too much`;
}

// "Split (3 parts)" for a list, and the hover text naming each part: "Groceries $40.00; Household $10.00".
export const splitLabel = (t) => `Split (${t.splits.length} parts)`;
export const splitHover = (t, categoryNames, format) =>
  t.splits.map((p) => `${categoryNames.get(p.category_id) || "Category"} ${format(Math.abs(p.amount_cents))}` +
    `${p.note ? ` (${p.note})` : ""}`).join("; ");
