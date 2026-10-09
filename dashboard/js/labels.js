// Plain-English names for the codes the Home Base uses.

export const ACCOUNT_KINDS = [
  ["checking", "Checking"], ["savings", "Savings"], ["credit_card", "Credit card"], ["cash", "Cash"],
  ["loan", "Loan"], ["brokerage", "Brokerage (stocks)"], ["retirement", "Retirement"], ["hsa", "HSA"],
  ["other", "Other"],
];

// What kind of retirement account (retirement accounts only).
export const RETIREMENT_TYPES = [
  ["roth_ira", "Roth IRA"], ["traditional_ira", "Traditional IRA"], ["401k", "401(k)"], ["roth_401k", "Roth 401(k)"],
  ["403b", "403(b)"], ["other", "Other retirement"],
];
export const retirementTypeLabel = (type) => (type ? lookup(RETIREMENT_TYPES, type) : "");

// "transfer" is built in and can't be chosen when adding a category.
export const GROUPS = [["needs", "Needs"], ["wants", "Wants"], ["savings", "Savings"], ["income", "Income"]];

const lookup = (pairs, code) => (pairs.find(([c]) => c === code) || [code, code])[1];

export const kindLabel = (kind) => lookup(ACCOUNT_KINDS, kind);
export const groupLabel = (group) => (group === "transfer" ? "Transfer" : lookup(GROUPS, group));
export const donationKindLabel = (kind) => (kind === "cash" ? "Cash" : "Goods");

export const DEDUCTION_KINDS = [
  ["medical", "Medical"], ["mortgage_interest", "Mortgage interest"], ["property_tax", "Property tax"],
  ["state_local_tax", "State and local taxes"], ["student_loan_interest", "Student loan interest"],
  ["hsa", "Health savings account"], ["ira", "IRA contributions"], ["education", "Education"],
  ["childcare", "Childcare"], ["home_office", "Home office"], ["other", "Other"],
];
export const deductionKindLabel = (kind) => lookup(DEDUCTION_KINDS, kind);

// What kind of transfer a linked pair is (server app/transfer_types.py).
export const TRANSFER_TYPES = [
  ["card_payment", "Credit card payment"], ["loan_payment", "Loan payment"], ["to_savings", "Into savings"],
  ["to_investments", "Into investments"], ["to_retirement", "Into retirement"], ["to_hsa", "Into HSA"],
  ["from_savings", "Out of savings"], ["from_investments", "Out of investments"],
  ["from_retirement", "Out of retirement"], ["from_hsa", "Out of HSA"], ["between_accounts", "Between accounts"],
];
export const transferTypeLabel = (type) => lookup(TRANSFER_TYPES, type);

export const NOT_TAX_ADVICE = "Estimate, not tax advice.";

// Everyday accounts first (checking, savings, card, cash), so a picker for spending or a bank file starts on one.
// Keeps the Home Base's order otherwise.
const EVERYDAY = ["checking", "savings", "credit_card", "cash"];
const everydayRank = (kind) => (EVERYDAY.includes(kind) ? EVERYDAY.indexOf(kind) : EVERYDAY.length);
export const everydayFirst = (accounts) =>
  accounts.map((a, i) => [a, i]).sort(([a, i], [b, j]) => everydayRank(a.kind) - everydayRank(b.kind) || i - j)
    .map(([a]) => a);

// What backs up a stock purchase or sale (server services/holdings_check.py).
export const checkedLabel = (checkedBy) => ({
  transaction: "A transaction",
  positions_file: "Broker's positions file",
}[checkedBy] || "Not verified yet");
export const notVerified = (records) => records.filter((r) => !r.checked_by);
