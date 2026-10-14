/**
 * Receipt photos waiting to go home, one encrypted file each in the app's own folder
 * (`receipts/<client_id>.bin`), sealed with the phone-only key (`sync/cacheCrypto.ts`). A photo is
 * never written in the clear; one that won't open reads as missing.
 */

import { Directory, File, Paths } from 'expo-file-system';

import { openBytesFromDisk, sealBytesForDisk } from '@/sync/cacheCrypto';

const CLIENT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function folder(): Directory {
  const dir = new Directory(Paths.document, 'receipts');
  dir.create({ idempotent: true, intermediates: true });
  return dir;
}

/** A receipt ID as the contract makes them (lowercase UUID v4); only these name files. */
export function isReceiptId(clientId: string): boolean {
  return CLIENT_ID.test(clientId);
}

function fileFor(clientId: string): File {
  // The ID names the file, so only a real UUID gets near the file system.
  if (!isReceiptId(clientId)) throw new Error('Not a receipt ID');
  return new File(folder(), `${clientId}.bin`);
}

const SUFFIX = '.bin';

/** The IDs of every photo file in the folder. Never throws. */
export function listPhotoIds(): string[] {
  try {
    return folder()
      .list()
      .map((entry) => entry.name)
      .filter((name) => name.endsWith(SUFFIX))
      .map((name) => name.slice(0, -SUFFIX.length))
      .filter(isReceiptId);
  } catch {
    return [];
  }
}

/** Save a photo (JPEG bytes) sealed. Throws if it can't be sealed or written: nothing plain is left. */
export async function writePhoto(clientId: string, jpeg: Uint8Array): Promise<void> {
  const sealed = await sealBytesForDisk(jpeg);
  fileFor(clientId).write(sealed);
}

/** The photo's JPEG bytes, or null if it's missing or can't be opened. Never throws. */
export async function readPhoto(clientId: string): Promise<Uint8Array | null> {
  try {
    const file = fileFor(clientId);
    if (!file.exists) return null;
    return await openBytesFromDisk(await file.bytes());
  } catch {
    return null;
  }
}

/** Delete the photo's file, if there is one. Never throws. */
export function deletePhoto(clientId: string): void {
  try {
    const file = fileFor(clientId);
    if (file.exists) file.delete();
  } catch {
    // Already gone, or a bad ID: nothing to delete.
  }
}
