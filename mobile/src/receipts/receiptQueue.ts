/**
 * The receipts waiting to go to the Home Base (roadmap #20, contract §6). The list (details only) is
 * sealed in AsyncStorage as `budgetbuddy.receipts.v1`; each photo is its own sealed file
 * (`receiptFiles.ts`). Changes run one at a time, so two quick edits never undo each other.
 *
 * A receipt stays until the Home Base answers `accepted` or `duplicate`. A `rejected` one stays, marked
 * with the Home Base's message, until you retake or delete it.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import { openFromDisk, sealForDisk } from '@/sync/cacheCrypto';

import { deletePhoto, isReceiptId, listPhotoIds, writePhoto } from './receiptFiles';

export const QUEUE_KEY = 'budgetbuddy.receipts.v1';

export type DeductionKind = 'donation' | 'medical' | 'business' | 'other';

/** What you typed about a receipt (all optional but the photo), as contract §6.2 sends it. */
export interface ReceiptDetails {
  merchant: string | null; // <= 100 characters
  total_cents: number | null; // whole cents, 0 or more
  category_id: number | null; // from the last snapshot
  note: string | null; // <= 500 characters
  tax_deductible: boolean;
  deduction_kind: DeductionKind | null;
}

export interface QueuedReceipt extends ReceiptDetails {
  client_id: string; // UUID v4, made when the photo was taken; the upload's idempotency key
  captured_at: string; // RFC 3339, when the photo was taken
  width: number;
  height: number;
  photo_bytes: number; // the JPEG's size, for batching
  state: 'waiting' | 'rejected';
  message: string | null; // the Home Base's plain-English reason, when rejected
}

let lastChange: Promise<unknown> = Promise.resolve();

/** Run `change` after any change already under way. */
function inTurn<T>(change: () => Promise<T>): Promise<T> {
  const next = lastChange.catch(() => undefined).then(change);
  lastChange = next;
  return next;
}

/**
 * The stored list. Throws if there is one that can't be read (locked phone, damaged), so a change never
 * saves over receipts it couldn't see.
 */
async function loadList(): Promise<QueuedReceipt[]> {
  const sealed = await AsyncStorage.getItem(QUEUE_KEY);
  if (sealed === null) return [];
  const text = await openFromDisk(sealed);
  if (text === null) throw new Error("The receipt list couldn't be read.");
  const list: unknown = JSON.parse(text);
  if (!Array.isArray(list)) throw new Error("The receipt list couldn't be read.");
  return list as QueuedReceipt[];
}

/** Every queued receipt, oldest first, for showing. A list that can't be read shows as empty. */
export async function listReceipts(): Promise<QueuedReceipt[]> {
  try {
    return await loadList();
  } catch {
    return [];
  }
}

async function saveList(list: QueuedReceipt[]): Promise<void> {
  if (list.length === 0) await AsyncStorage.removeItem(QUEUE_KEY);
  else await AsyncStorage.setItem(QUEUE_KEY, await sealForDisk(JSON.stringify(list)));
}

export const MAX_PHOTO_BYTES = 3 * 1024 * 1024; // contract §6.1
export const PHOTO_PROBLEM = "This photo can't be saved. Please take it again.";

/** A JPEG within the Home Base's limit (contract §6.1: at most 3 MiB, starting FF D8 FF). */
export function photoFits(jpeg: Uint8Array): boolean {
  return jpeg.length > 3 && jpeg.length <= MAX_PHOTO_BYTES && jpeg[0] === 0xff && jpeg[1] === 0xd8 && jpeg[2] === 0xff;
}

/** Queue a photo with its details. Throws (with a plain message) if it can't be saved; nothing is left behind. */
export function addReceipt(
  receipt: Omit<QueuedReceipt, 'state' | 'message' | 'photo_bytes'>,
  jpeg: Uint8Array,
): Promise<void> {
  if (!isReceiptId(receipt.client_id) || !photoFits(jpeg)) return Promise.reject(new Error(PHOTO_PROBLEM));
  return inTurn(async () => {
    const list = await loadList();
    if (list.some((r) => r.client_id === receipt.client_id)) throw new Error(PHOTO_PROBLEM);
    try {
      await writePhoto(receipt.client_id, jpeg);
      await saveList([...list, { ...receipt, photo_bytes: jpeg.length, state: 'waiting', message: null }]);
    } catch {
      deletePhoto(receipt.client_id);
      throw new Error(PHOTO_PROBLEM);
    }
  }).catch(() => {
    throw new Error(PHOTO_PROBLEM); // one plain message, whatever went wrong
  });
}

/** Take receipts off the queue (sent, or deleted by you), photos too. */
export function removeReceipts(clientIds: string[]): Promise<void> {
  if (clientIds.length === 0) return Promise.resolve();
  return inTurn(async () => {
    const gone = new Set(clientIds);
    await saveList((await loadList()).filter((r) => !gone.has(r.client_id)));
    for (const id of gone) deletePhoto(id);
  });
}

/** Mark receipts the Home Base turned down, each with its message. */
export function markRejected(messages: Map<string, string>): Promise<void> {
  if (messages.size === 0) return Promise.resolve();
  return inTurn(async () => {
    const list = await loadList();
    await saveList(
      list.map((r) => (messages.has(r.client_id) ? { ...r, state: 'rejected', message: messages.get(r.client_id) ?? null } : r)),
    );
  });
}

/**
 * Delete photo files no receipt lists (left by an app that stopped between saving a photo and the list,
 * or the other way round). Run once at app start, after any change under way. Never throws.
 */
export function cleanUpPhotos(): Promise<void> {
  return inTurn(async () => {
    const listed = new Set((await loadList()).map((r) => r.client_id));
    for (const id of listPhotoIds()) if (!listed.has(id)) deletePhoto(id);
  }).catch(() => undefined);
}

/** How many receipts are waiting to go home (for the reminder's text). Never throws. */
export async function waitingCount(): Promise<number> {
  return (await listReceipts()).filter((r) => r.state === 'waiting').length;
}

/** False when there's a saved list this phone can't open (its key is gone, say after a restore). */
export async function queueReadable(): Promise<boolean> {
  try {
    await loadList();
    return true;
  } catch {
    return false;
  }
}

/**
 * Throw away every waiting receipt and photo. Offered only when the list can't be opened: then nothing
 * in it can be read or sent, and new photos couldn't be added.
 */
export function clearQueue(): Promise<void> {
  return inTurn(async () => {
    await AsyncStorage.removeItem(QUEUE_KEY);
    for (const id of listPhotoIds()) deletePhoto(id);
  });
}
