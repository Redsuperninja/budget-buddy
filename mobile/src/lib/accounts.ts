/** Plain-English labels and balance wording for accounts. Debt accounts show negative balances as "owed". */

import { formatCents } from '@/lib/money';
import type { AccountKind, SnapshotAccount } from '@/sync/snapshot';

const KIND_LABELS: Record<AccountKind, string> = {
  checking: 'Checking',
  savings: 'Savings',
  brokerage: 'Investments',
  credit_card: 'Credit card',
  cash: 'Cash',
  loan: 'Loan',
  retirement: 'Retirement',
  hsa: 'Health savings (HSA)',
  other: 'Other account',
};

export function accountKindLabel(kind: AccountKind): string {
  return KIND_LABELS[kind];
}

/** Cards and loans: negative means money owed (docs/dev/architecture/ledger.md, "Signs and balances"). */
export function isDebtKind(kind: AccountKind): boolean {
  return kind === 'credit_card' || kind === 'loan';
}

/**
 * "$50.00 owed" for a card/loan in debt, "$12.00 credit" for an overpaid card, "$30.00 overdrawn" for
 * any other account below zero (contract §5.1: negative means money owed), else plain money.
 */
export function formatAccountBalance(account: Pick<SnapshotAccount, 'kind' | 'balance_cents'>, currency = 'USD'): string {
  const { kind, balance_cents: cents } = account;
  if (isDebtKind(kind) && cents < 0) return `${formatCents(-cents, currency)} owed`;
  if (isDebtKind(kind) && cents > 0) return `${formatCents(cents, currency)} credit`;
  if (cents < 0) return `${formatCents(-cents, currency)} overdrawn`;
  return formatCents(cents, currency);
}

/** Money owed on this account: a card or loan in debt, or any other account overdrawn. */
export function isOwing(account: Pick<SnapshotAccount, 'balance_cents'>): boolean {
  return account.balance_cents < 0;
}

/** "1 account needs an app update to show." or null when every account is shown. */
export function skippedAccountsNote(count: number | undefined): string | null {
  if (!count || count <= 0) return null;
  return count === 1
    ? '1 account needs an app update to show. Update Budget Buddy on this phone.'
    : `${count} accounts need an app update to show. Update Budget Buddy on this phone.`;
}

/** "3 transactions need a category on your computer." or null when there is nothing to say. */
export function unassignedNote(count: number | undefined): string | null {
  if (!count || count <= 0) return null;
  return count === 1
    ? '1 transaction needs a category on your computer.'
    : `${count} transactions need a category on your computer.`;
}

export const UNASSIGNED_NOT_COUNTED = 'They are not counted in Spent or Left to spend.';
