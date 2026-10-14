/** Turning what you typed about a receipt into `ReceiptDetails` (contract §6.2), with plain messages. */

import { parseDollars } from '@/lib/money';

import type { DeductionKind, ReceiptDetails } from './receiptQueue';

export const MERCHANT_MAX = 100;
export const NOTE_MAX = 500;
export const DEDUCTION_KINDS: readonly { kind: DeductionKind; label: string }[] = [
  { kind: 'medical', label: 'Medical' },
  { kind: 'donation', label: 'Donation' },
  { kind: 'business', label: 'Business' },
  { kind: 'other', label: 'Other' },
];

export type ReceiptFields = {
  merchant: string;
  total: string; // as typed: "23.99", "$1,200", or empty
  categoryId: number | null;
  note: string;
  taxDeductible: boolean;
  deductionKind: DeductionKind | null;
};

export const EMPTY_FIELDS: ReceiptFields = {
  merchant: '',
  total: '',
  categoryId: null,
  note: '',
  taxDeductible: false,
  deductionKind: null,
};

const chars = (s: string) => [...s].length;
const orNull = (s: string) => (s.trim() === '' ? null : s.trim());

/** The details to queue, or a plain-English problem to show. Everything but the photo is optional. */
export function readFields(f: ReceiptFields): { details: ReceiptDetails } | { problem: string } {
  if (chars(f.merchant.trim()) > MERCHANT_MAX) {
    return { problem: `The store name can be at most ${MERCHANT_MAX} characters.` };
  }
  if (chars(f.note.trim()) > NOTE_MAX) return { problem: `The note can be at most ${NOTE_MAX} characters.` };
  let total: number | null = null;
  if (f.total.trim() !== '') {
    total = parseDollars(f.total);
    if (total === null) return { problem: 'Enter the total as an amount, like 23.99, or leave it empty.' };
  }
  return {
    details: {
      merchant: orNull(f.merchant),
      total_cents: total,
      category_id: f.categoryId,
      note: orNull(f.note),
      tax_deductible: f.taxDeductible,
      deduction_kind: f.taxDeductible ? (f.deductionKind ?? 'other') : null,
    },
  };
}
