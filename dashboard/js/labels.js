// Plain-English names for the codes the Home Base uses.

export const ACCOUNT_KINDS = [
  ["checking", "Checking"], ["savings", "Savings"], ["credit_card", "Credit card"], ["cash", "Cash"],
  ["loan", "Loan"], ["brokerage", "Brokerage (stocks)"], ["retirement", "Retirement"], ["hsa", "HSA"],
  ["other", "Other"],
];

// "transfer" is built in and can't be chosen when adding a category.
export const GROUPS = [["needs", "Needs"], ["wants", "Wants"], ["savings", "Savings"], ["income", "Income"]];

const lookup = (pairs, code) => (pairs.find(([c]) => c === code) || [code, code])[1];

export const kindLabel = (kind) => lookup(ACCOUNT_KINDS, kind);
export const groupLabel = (group) => (group === "transfer" ? "Transfer" : lookup(GROUPS, group));
export const donationKindLabel = (kind) => (kind === "cash" ? "Cash" : "Goods");

export const NOT_TAX_ADVICE = "Estimate, not tax advice.";
