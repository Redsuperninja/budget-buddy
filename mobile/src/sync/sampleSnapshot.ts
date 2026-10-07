import type { Snapshot } from './snapshot';

/**
 * A made-up snapshot shown until the phone is paired and has synced once.
 *
 * Everything here is FICTIONAL (people, places, amounts). It is not anyone's real financial data.
 * Group totals add up to their categories, and budget totals add up to the groups, so the
 * screens look the way they will with real data. "Eating out" is deliberately over its target
 * so the "over budget" state is visible.
 */
export const SAMPLE_SNAPSHOT: Snapshot = {
  contract: 1,
  server_id: 'sample-data-not-a-real-computer',
  generated_at: '2026-10-18T17:00:00Z',
  currency: 'USD',
  period: {
    month: '2026-10',
    start: '2026-10-01',
    end: '2026-10-31',
    days_elapsed: 18,
    days_in_month: 31,
  },
  income: {
    expected_cents: 520000,
    received_cents: 520000,
    last_paycheck: { pay_date: '2026-10-15', net_cents: 260000 },
  },
  budget: {
    target_cents: 520000,
    actual_cents: 356027,
    unassigned: { in_cents: 0, out_cents: 4599, count: 2 },
    groups: [
      {
        group: 'needs',
        name: 'Needs',
        target_cents: 260000,
        actual_cents: 225680,
        categories: [
          { id: 1, name: 'Rent', target_cents: 150000, actual_cents: 150000 },
          { id: 2, name: 'Groceries', target_cents: 60000, actual_cents: 41230 },
          { id: 3, name: 'Utilities', target_cents: 18000, actual_cents: 12600 },
          { id: 4, name: 'Getting around', target_cents: 20000, actual_cents: 9850 },
          { id: 5, name: 'Phone and internet', target_cents: 12000, actual_cents: 12000 },
        ],
      },
      {
        group: 'wants',
        name: 'Wants',
        target_cents: 156000,
        actual_cents: 70347,
        categories: [
          { id: 6, name: 'Eating out', target_cents: 30000, actual_cents: 34200 },
          { id: 7, name: 'Fun and hobbies', target_cents: 20000, actual_cents: 8500 },
          { id: 8, name: 'Shopping', target_cents: 40000, actual_cents: 22150 },
          { id: 9, name: 'Subscriptions', target_cents: 6000, actual_cents: 5497 },
          { id: 10, name: 'Travel', target_cents: 60000, actual_cents: 0 },
        ],
      },
      {
        group: 'savings',
        name: 'Savings',
        target_cents: 104000,
        actual_cents: 60000,
        categories: [
          { id: 11, name: 'Emergency fund', target_cents: 50000, actual_cents: 50000 },
          { id: 12, name: 'Retirement extra', target_cents: 34000, actual_cents: 0 },
          { id: 13, name: 'Vacation fund', target_cents: 20000, actual_cents: 10000 },
        ],
      },
    ],
  },
  transactions: [
    { id: 1015, date: '2026-10-18', description: 'Corner Cafe', amount_cents: -1475, category_id: 6, account_id: 1 },
    { id: 1014, date: '2026-10-17', description: 'Green Valley Market', amount_cents: -8642, category_id: 2, account_id: 1 },
    { id: 1013, date: '2026-10-16', description: 'Riverside Power and Light', amount_cents: -12600, category_id: 3, account_id: 1 },
    { id: 1012, date: '2026-10-15', description: 'Paycheck', amount_cents: 260000, category_id: null, account_id: 1 },
    { id: 1011, date: '2026-10-15', description: 'Move to Vacation fund', amount_cents: -10000, category_id: 13, account_id: 1 },
    { id: 1010, date: '2026-10-14', description: 'Starlight Cinema', amount_cents: -3400, category_id: 7, account_id: 1 },
    { id: 1009, date: '2026-10-12', description: 'Fuel Stop', amount_cents: -4850, category_id: 4, account_id: 1 },
    { id: 1008, date: '2026-10-11', description: 'Noodle House', amount_cents: -6230, category_id: 6, account_id: 1 },
    { id: 1007, date: '2026-10-09', description: 'Streamly', amount_cents: -1599, category_id: 9, account_id: 1 },
    { id: 1006, date: '2026-10-08', description: 'Green Valley Market', amount_cents: -11420, category_id: 2, account_id: 1 },
    { id: 1005, date: '2026-10-05', description: 'Maple Street Books', amount_cents: -2750, category_id: 8, account_id: 1 },
    { id: 1004, date: '2026-10-03', description: 'Move to Emergency fund', amount_cents: -50000, category_id: 11, account_id: 1 },
    { id: 1003, date: '2026-10-01', description: 'Maple Court Apartments', amount_cents: -150000, category_id: 1, account_id: 1 },
    { id: 1002, date: '2026-10-01', description: 'Pine Mobile', amount_cents: -12000, category_id: 5, account_id: 1 },
    { id: 1001, date: '2026-10-01', description: 'Paycheck', amount_cents: 260000, category_id: null, account_id: 1 },
  ],
  accounts: [
    { id: 1, name: 'Everyday checking', kind: 'checking', balance_cents: 284315, balance_as_of: '2026-10-18' },
    { id: 2, name: 'Rainy day', kind: 'savings', balance_cents: 960000, balance_as_of: '2026-10-15' },
    { id: 3, name: 'Blue travel card', kind: 'credit_card', balance_cents: -5000, balance_as_of: '2026-10-17' },
  ],
  tax: {
    year: 2026,
    donations_total_cents: 45000,
    realized_gains: { short_term_cents: -12000, long_term_cents: 84000, is_estimate: true },
    deductions: [
      { kind: 'medical', label: 'Medical', amount_cents: 23000, is_estimate: false },
      { kind: 'home_office', label: 'Home office', amount_cents: 51000, is_estimate: true },
    ],
    disclaimer: "These totals help you get ready for tax time. They aren't tax advice.",
  },
  settings: { reminder_days_default: 2, reminder_days_allowed: [1, 2, 3] },
};
