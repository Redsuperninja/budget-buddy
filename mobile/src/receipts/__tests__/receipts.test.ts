/** The receipt queue and its upload (roadmap #20). Made-up data only. */
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as FileSystem from 'expo-file-system';

import {
  addReceipt,
  cleanUpPhotos,
  clearQueue,
  queueReadable,
  listReceipts,
  MAX_PHOTO_BYTES,
  PHOTO_PROBLEM,
  QUEUE_KEY,
  removeReceipts,
  waitingCount,
} from '../receiptQueue';
import type { QueuedReceipt } from '../receiptQueue';
import { batches, MAX_BATCH_BYTES, uploadReceipts } from '../receiptUpload';
import { readPhoto } from '../receiptFiles';

const files = (FileSystem as unknown as { __files: Map<string, Uint8Array> }).__files;
const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3, 4, 5]);
let n = 0;
const nextId = () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;

function receipt(overrides: Partial<QueuedReceipt> = {}) {
  return {
    client_id: nextId(),
    captured_at: '2026-10-01T12:14:03Z',
    merchant: 'Fake Corner Pharmacy',
    total_cents: 2399,
    category_id: 4,
    note: null,
    tax_deductible: true,
    deduction_kind: 'medical' as const,
    width: 1200,
    height: 1600,
    ...overrides,
  };
}

beforeEach(async () => {
  await AsyncStorage.clear();
  files.clear();
});

describe('receipt queue', () => {
  it('keeps the details and the photo encrypted on the phone', async () => {
    const r = receipt();
    await addReceipt(r, JPEG);
    const [saved] = await listReceipts();
    expect(saved).toMatchObject({ client_id: r.client_id, merchant: 'Fake Corner Pharmacy', state: 'waiting', photo_bytes: JPEG.length });
    expect(await AsyncStorage.getItem(QUEUE_KEY)).not.toContain('Pharmacy');
    const [stored] = [...files.values()];
    expect([...stored.subarray(0, 3)]).not.toEqual([0xff, 0xd8, 0xff]);
    expect(await readPhoto(r.client_id)).toEqual(JPEG);
  });

  it('removes a receipt and its photo', async () => {
    const r = receipt();
    await addReceipt(r, JPEG);
    await removeReceipts([r.client_id]);
    expect(await listReceipts()).toEqual([]);
    expect(files.size).toBe(0);
  });
});

describe('receipt queue safety', () => {
  it('refuses a photo too big for the Home Base, one that is not a JPEG, or a repeated ID', async () => {
    const big = new Uint8Array(MAX_PHOTO_BYTES + 1);
    big.set([0xff, 0xd8, 0xff]);
    await expect(addReceipt(receipt(), big)).rejects.toThrow(PHOTO_PROBLEM);
    await expect(addReceipt(receipt(), new Uint8Array([0x89, 0x50, 0x4e, 0x47, 1]))).rejects.toThrow(PHOTO_PROBLEM);
    const r = receipt();
    await addReceipt(r, JPEG);
    await expect(addReceipt(r, JPEG)).rejects.toThrow(PHOTO_PROBLEM);
    expect(await listReceipts()).toHaveLength(1);
    expect(files.size).toBe(1);
  });

  it('never saves over a list it could not read', async () => {
    await addReceipt(receipt(), JPEG);
    const sealed = (await AsyncStorage.getItem(QUEUE_KEY)) as string;
    const damaged = JSON.stringify({ ...JSON.parse(sealed), c: 'AAAA' });
    await AsyncStorage.setItem(QUEUE_KEY, damaged);
    await expect(addReceipt(receipt(), JPEG)).rejects.toThrow(PHOTO_PROBLEM);
    expect(await AsyncStorage.getItem(QUEUE_KEY)).toBe(damaged); // not replaced by a one-receipt list
  });

  it('cleans up photo files no receipt lists, and counts what is waiting', async () => {
    const kept = receipt();
    await addReceipt(kept, JPEG);
    files.set('doc/receipts/00000000-0000-4000-8000-999999999999.bin', new Uint8Array([1, 2, 3]));
    expect(await cleanUpPhotos()).toBe(1); // the waiting count, read with the same list
    expect([...files.keys()]).toEqual([`doc/receipts/${kept.client_id}.bin`]);
    expect(await waitingCount()).toBe(1);
  });
});

describe('receipt batches', () => {
  const queued = (photoBytes: number): QueuedReceipt => ({
    ...receipt(), photo_bytes: photoBytes, state: 'waiting', message: null,
  });

  it('holds at most 5 receipts', () => {
    const list = Array.from({ length: 7 }, () => queued(1000));
    expect(batches(list).map((b) => b.length)).toEqual([5, 2]);
  });

  it('starts a new batch before the request gets too big', () => {
    const big = 3 * 1024 * 1024; // the largest photo the Home Base takes
    const sizes = batches([queued(big), queued(big), queued(big)]).map((b) => b.length);
    expect(sizes).toEqual([2, 1]);
    expect(MAX_BATCH_BYTES).toBeLessThan(12 * 1024 * 1024);
  });

  it('skips rejected receipts', () => {
    expect(batches([{ ...queued(10), state: 'rejected' }])).toEqual([]);
  });
});

describe('uploadReceipts', () => {
  it('sends waiting receipts and applies each answer', async () => {
    const [a, b, c] = [receipt(), receipt(), receipt()];
    for (const r of [a, b, c]) await addReceipt(r, JPEG);
    const send = jest.fn(async (data: { receipts: any[] }) => {
      expect(data.receipts.map((x) => x.client_id)).toEqual([a.client_id, b.client_id, c.client_id]);
      expect(data.receipts[0].image).toMatchObject({ mime: 'image/jpeg', width: 1200, height: 1600 });
      return {
        results: [
          { client_id: a.client_id, status: 'accepted', receipt_id: 57 },
          { client_id: b.client_id, status: 'duplicate', receipt_id: 41 },
          { client_id: c.client_id, status: 'rejected', reason: 'image_invalid', message: "This photo\u202e couldn't be read." },
          { client_id: 'someone-else', status: 'accepted' },
        ],
      };
    });

    expect(await uploadReceipts(send)).toBe(2);
    const left = await listReceipts();
    expect(left).toHaveLength(1);
    expect(left[0]).toMatchObject({ client_id: c.client_id, state: 'rejected', message: "This photo couldn't be read." });
    expect(await readPhoto(a.client_id)).toBeNull(); // sent: photo gone

    send.mockClear();
    expect(await uploadReceipts(send)).toBe(0); // a rejected receipt waits for you
    expect(send).not.toHaveBeenCalled();
  });

  it('only takes off the queue what was actually sent', async () => {
    const [kept, sent] = [receipt(), receipt()];
    await addReceipt(kept, JPEG);
    await addReceipt(sent, JPEG);
    files.delete(`doc/receipts/${kept.client_id}.bin`); // this one can't be sent
    const send = jest.fn(async () => ({
      results: [kept, sent].map((r) => ({ client_id: r.client_id, status: 'accepted' })),
    }));
    expect(await uploadReceipts(send)).toBe(1);
    expect((await listReceipts()).map((r) => r.client_id)).toEqual([kept.client_id]);
  });

  it('marks a receipt whose photo is gone without sending it', async () => {
    const r = receipt();
    await addReceipt(r, JPEG);
    files.clear();
    const send = jest.fn();
    expect(await uploadReceipts(send)).toBe(0);
    expect(send).not.toHaveBeenCalled();
    expect((await listReceipts())[0]).toMatchObject({ state: 'rejected' });
  });

  it('keeps everything queued when the request fails', async () => {
    await addReceipt(receipt(), JPEG);
    await expect(uploadReceipts(async () => { throw new Error('offline'); })).rejects.toThrow('offline');
    expect((await listReceipts())[0]).toMatchObject({ state: 'waiting' });
  });
});

describe('a list this phone can no longer open', () => {
  it('can be cleared, so new photos can be added again', async () => {
    await addReceipt(receipt(), JPEG);
    const sealed = (await AsyncStorage.getItem(QUEUE_KEY)) as string;
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify({ ...JSON.parse(sealed), c: 'AAAA' }));
    expect(await queueReadable()).toBe(false);
    await clearQueue();
    expect(await queueReadable()).toBe(true);
    expect(files.size).toBe(0);
    await addReceipt(receipt(), JPEG);
    expect(await listReceipts()).toHaveLength(1);
  });
});
