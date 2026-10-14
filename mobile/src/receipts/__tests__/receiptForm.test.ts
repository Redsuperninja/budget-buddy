import { parseDollars } from '@/lib/money';

import { EMPTY_FIELDS, readFields } from '../receiptForm';
import * as FileSystem from 'expo-file-system';

import { resizeFor, sweepPhotoCaches } from '../photo';

describe('parseDollars', () => {
  it.each([
    ['23.99', 2399], ['$1,200', 120000], ['.50', 50], ['12.', 1200], [' 7 ', 700], ['0', 0],
  ])('%s -> %i cents', (text, cents) => expect(parseDollars(text)).toBe(cents));

  it.each(['', '-5', '1.005', 'abc', '.', '1e3', '12..3'])('refuses %p', (text) => expect(parseDollars(text)).toBeNull());
});

describe('readFields', () => {
  it('everything but the photo is optional', () => {
    expect(readFields(EMPTY_FIELDS)).toEqual({
      details: { merchant: null, total_cents: null, category_id: null, note: null, tax_deductible: false, deduction_kind: null },
    });
  });

  it('reads what you typed, with "other" when deductible but no kind picked', () => {
    const got = readFields({ ...EMPTY_FIELDS, merchant: ' Fake Pharmacy ', total: '23.99', categoryId: 4, taxDeductible: true });
    expect(got).toEqual({
      details: { merchant: 'Fake Pharmacy', total_cents: 2399, category_id: 4, note: null, tax_deductible: true, deduction_kind: 'other' },
    });
    const notDeductible = readFields({ ...EMPTY_FIELDS, deductionKind: 'medical' });
    expect('details' in notDeductible && notDeductible.details.deduction_kind).toBeNull();
  });

  it('says plainly what is wrong', () => {
    expect(readFields({ ...EMPTY_FIELDS, total: 'twelve' })).toEqual({
      problem: 'Enter the total as an amount, like 23.99, or leave it empty.',
    });
    expect('problem' in readFields({ ...EMPTY_FIELDS, merchant: 'x'.repeat(101) })).toBe(true);
    expect('problem' in readFields({ ...EMPTY_FIELDS, note: 'x'.repeat(501) })).toBe(true);
  });
});

describe('resizeFor', () => {
  it('brings the longest edge down to 1600 px, or leaves a small photo alone', () => {
    expect(resizeFor(3024, 4032)).toEqual({ height: 1600 });
    expect(resizeFor(4032, 3024)).toEqual({ width: 1600 });
    expect(resizeFor(1200, 1600)).toBeNull();
  });
});

describe('sweepPhotoCaches', () => {
  it("deletes plain photos the camera or the resizer left behind, and nothing else", () => {
    const files = (FileSystem as unknown as { __files: Map<string, Uint8Array> }).__files;
    files.clear();
    files.set('cache/Camera/left.jpg', new Uint8Array([0xff, 0xd8, 0xff]));
    files.set('cache/ImageManipulator/left.jpg', new Uint8Array([0xff, 0xd8, 0xff]));
    files.set('doc/receipts/00000000-0000-4000-8000-000000000001.bin', new Uint8Array([1]));
    sweepPhotoCaches();
    expect([...files.keys()]).toEqual(['doc/receipts/00000000-0000-4000-8000-000000000001.bin']);
  });
});
