/**
 * Sending queued receipts home during a sync (contract §6 and §8 step 2). Waiting receipts go in
 * batches of 1 to 5 whose encrypted request stays under the Home Base's 12 MiB limit; a photo is read
 * (and opened) only for its own batch. `accepted` and `duplicate` come off the queue; `rejected` stay,
 * marked with the Home Base's message. Rejected receipts aren't sent again until you retake them.
 *
 * `send` posts one batch through the encrypted envelope (`syncClient` supplies it), so nothing here
 * knows a key.
 */

import { b64uEncode } from '@/sync/base64url';
import { cleanText } from '@/sync/snapshotChecks';

import { readPhoto } from './receiptFiles';
import { listReceipts, markRejected, removeReceipts } from './receiptQueue';
import type { QueuedReceipt } from './receiptQueue';

export const MAX_BATCH_ITEMS = 5;
export const MAX_BATCH_BYTES = 11 * 1024 * 1024; // under the 12 MiB body limit, with room to spare
const DETAILS_BYTES = 2048; // generous room for one receipt's JSON fields
const MESSAGE_MAX = 200;

export type SendBatch = (data: { receipts: object[] }) => Promise<Record<string, unknown>>;

/** About how big a receipt makes the encrypted request: base64url inside, then the sealed envelope. */
export function encodedSize(r: Pick<QueuedReceipt, 'photo_bytes'>): number {
  const inner = Math.ceil((r.photo_bytes * 4) / 3) + DETAILS_BYTES;
  return Math.ceil(((inner + 16) * 4) / 3);
}

/** Waiting receipts in order, split into batches of 1-5 that fit `MAX_BATCH_BYTES`. */
export function batches(receipts: QueuedReceipt[]): QueuedReceipt[][] {
  const out: QueuedReceipt[][] = [];
  let current: QueuedReceipt[] = [];
  let size = 0;
  for (const r of receipts.filter((x) => x.state === 'waiting')) {
    const s = encodedSize(r);
    if (current.length > 0 && (current.length === MAX_BATCH_ITEMS || size + s > MAX_BATCH_BYTES)) {
      out.push(current);
      current = [];
      size = 0;
    }
    current.push(r);
    size += s;
  }
  if (current.length > 0) out.push(current);
  return out;
}

async function asUpload(r: QueuedReceipt): Promise<object | null> {
  const jpeg = await readPhoto(r.client_id);
  if (!jpeg) return null;
  return {
    client_id: r.client_id,
    captured_at: r.captured_at,
    merchant: r.merchant,
    total_cents: r.total_cents,
    category_id: r.category_id,
    note: r.note,
    tax_deductible: r.tax_deductible,
    deduction_kind: r.tax_deductible ? r.deduction_kind : null,
    image: { mime: 'image/jpeg', width: r.width, height: r.height, data: b64uEncode(jpeg) },
  };
}

const PHOTO_LOST = "This photo couldn't be read on your phone. Please take it again.";

/**
 * Send every waiting receipt. Returns how many the Home Base now has (accepted or duplicate). A
 * failed request throws (the sync reports it); receipts already answered stay answered.
 */
export async function uploadReceipts(send: SendBatch): Promise<number> {
  let stored = 0;
  for (const batch of batches(await listReceipts())) {
    const lost = new Map<string, string>();
    const items: object[] = [];
    const sentIds = new Set<string>();
    for (const r of batch) {
      const upload = await asUpload(r);
      if (upload) {
        items.push(upload);
        sentIds.add(r.client_id);
      } else lost.set(r.client_id, PHOTO_LOST);
    }
    await markRejected(lost);
    if (items.length === 0) continue;

    const answer = await send({ receipts: items });
    const done: string[] = [];
    const rejected = new Map<string, string>();
    for (const result of Array.isArray(answer.results) ? answer.results : []) {
      const { client_id: id, status, message } = (result ?? {}) as Record<string, unknown>;
      if (typeof id !== 'string' || !sentIds.has(id)) continue; // only answers about what we sent
      if (status === 'accepted' || status === 'duplicate') done.push(id);
      else if (status === 'rejected') {
        const words = typeof message === 'string' ? cleanText(message, MESSAGE_MAX) : '';
        rejected.set(id, words || PHOTO_LOST);
      }
    }
    await removeReceipts(done);
    await markRejected(rejected);
    stored += done.length;
  }
  return stored;
}
