// The Starter budget step of Setup (roadmap 25h, ADR-0015). Pure: no page, no network.

import { parseDollars } from "./money.js";

// Only these groups can be unticked. Income categories (Paycheck...) and Transfer stay, because pay and moves
// between accounts are filed under them.
export const CHOOSABLE_GROUPS = ["needs", "wants", "savings"];

// The categories offered as ticks, in group order: [{ group, categories }].
export function choosable(categories) {
  return CHOOSABLE_GROUPS
    .map((group) => ({ group, categories: categories.filter((c) => c.group === group) }))
    .filter((g) => g.categories.length);
}

// The monthly take-home pay typed in the box: { cents } (a blank box means leave it alone, cents null), or { error }.
export function takeHomeFromText(text) {
  if (String(text).trim() === "") return { cents: null };
  const cents = parseDollars(text);
  if (cents === null || cents <= 0) {
    return { error: "Please enter your monthly take-home pay as a number above zero, like 3200.50." };
  }
  return { cents };
}

// The ids to remove: unticked categories in the groups above only.
export const toRemove = (categories, unticked) =>
  categories.filter((c) => unticked.has(c.id) && CHOOSABLE_GROUPS.includes(c.group)).map((c) => c.id);

// The sentence shown after saving. removed/kept: counts; income: cents or null.
export function savedSummary({ removed, kept, income }) {
  const parts = [];
  if (removed) parts.push(`Removed ${removed} ${removed === 1 ? "category" : "categories"}.`);
  if (kept) parts.push(`Kept ${kept} because ${kept === 1 ? "it already has" : "they already have"} transactions.`);
  if (income !== null) parts.push("Saved your monthly take-home pay.");
  return parts.length ? parts.join(" ") : "Nothing to change.";
}
