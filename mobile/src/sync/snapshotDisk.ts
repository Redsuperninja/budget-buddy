/**
 * Reading and writing the saved snapshot on the phone, always encrypted (`cacheCrypto`, issue #19).
 *
 * The sealed copy is `budgetbuddy.snapshot.v2`. Phones that saved before encryption have a plain-text
 * `budgetbuddy.snapshot.v1`: it's deleted as soon as it's read (even if it turns out to be unusable), and
 * the caller saves it again sealed. If that save fails, the phone asks for a sync like any time nothing is
 * saved. Saves run one at a time, in order, so an older copy never lands after a newer one. A copy far
 * bigger than any real snapshot isn't even read (it could freeze the screen; Android can't read back
 * about 2 MB).
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import { openFromDisk, sealForDisk } from './cacheCrypto';
import { SNAPSHOT_LIMITS } from './snapshot';

export const SNAPSHOT_STORAGE_KEY = 'budgetbuddy.snapshot.v2';
export const LEGACY_SNAPSHOT_KEY = 'budgetbuddy.snapshot.v1';
// Sealing adds the nonce, the box's tag and base64url (about a third more).
const MAX_SEALED_CHARS = Math.ceil(SNAPSHOT_LIMITS.storedChars * 1.5);

export type SavedText =
  | { kind: 'none' }
  | { kind: 'unreadable' }
  | { kind: 'text'; text: string; legacy: boolean };

/** The saved snapshot's JSON text, if any. Never throws. */
export async function readSaved(): Promise<SavedText> {
  try {
    const sealed = await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY);
    if (sealed !== null) {
      if (sealed.length > MAX_SEALED_CHARS) return { kind: 'unreadable' };
      const text = await openFromDisk(sealed);
      return text === null ? { kind: 'unreadable' } : { kind: 'text', text, legacy: false };
    }
    const plain = await AsyncStorage.getItem(LEGACY_SNAPSHOT_KEY);
    if (plain === null) return { kind: 'none' };
    await AsyncStorage.removeItem(LEGACY_SNAPSHOT_KEY); // never leave plain financial data behind
    if (plain.length > SNAPSHOT_LIMITS.storedChars) return { kind: 'unreadable' };
    return { kind: 'text', text: plain, legacy: true };
  } catch {
    return { kind: 'unreadable' };
  }
}

let lastWrite: Promise<void> = Promise.resolve();

/**
 * Save the snapshot's JSON text sealed, after any save already under way. Rejects if it can't be
 * sealed or saved (the caller shows a friendly message); nothing plain is ever written.
 */
export function writeSaved(text: string): Promise<void> {
  const write = lastWrite.catch(() => undefined).then(async () => {
    await AsyncStorage.setItem(SNAPSHOT_STORAGE_KEY, await sealForDisk(text));
    try {
      await AsyncStorage.removeItem(LEGACY_SNAPSHOT_KEY);
    } catch {
      // Already deleted when read; this only catches a copy written by a much older app version.
    }
  });
  lastWrite = write;
  return write;
}
