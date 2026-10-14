/**
 * Encrypting what the phone keeps on disk (issue #19). The saved budget (balances, 60 days of
 * transactions, tax totals) is sealed with its own random 32-byte key before it reaches AsyncStorage,
 * which Android and iOS can copy into cloud and computer backups.
 *
 * - The key lives in expo-secure-store as `budgetbuddy.cache_key.v1`, readable only while the phone is
 *   unlocked and only on this phone (`WHEN_UNLOCKED_THIS_DEVICE_ONLY`), so it's never in a backup and a
 *   restored backup holds only ciphertext. It's separate from the sync key.
 * - Each save uses `nacl.secretbox` with a fresh 24-byte nonce from the phone's secure random source;
 *   with no secure random source nothing is saved (never Math.random, never plain text).
 * - Stored as `{"v":1,"n":"<base64url nonce>","c":"<base64url box>"}` (strict base64url, contract §4.6).
 * - Anything that won't open (missing key, damaged box, wrong nonce length) is "nothing saved": the
 *   caller shows its friendly message and asks for a sync. Credentials are never touched here.
 */

import * as SecureStore from 'expo-secure-store';
import nacl from 'tweetnacl';
import { decodeUTF8, encodeUTF8 } from 'tweetnacl-util';

import { b64uDecode, b64uEncode } from './base64url';
import { randomBytes } from './transport';

export const CACHE_KEY_NAME = 'budgetbuddy.cache_key.v1';
const KEY_OPTIONS = { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY };

async function readKey(): Promise<Uint8Array | null> {
  const text = await SecureStore.getItemAsync(CACHE_KEY_NAME, KEY_OPTIONS);
  if (text === null) return null;
  try {
    return b64uDecode(text, nacl.secretbox.keyLength);
  } catch {
    return null;
  }
}

async function makeOrReadKey(): Promise<Uint8Array> {
  const existing = await readKey();
  if (existing) return existing;
  let key: Uint8Array;
  try {
    key = randomBytes(nacl.secretbox.keyLength);
  } catch {
    throw new Error('No secure random source: nothing is saved.');
  }
  await SecureStore.setItemAsync(CACHE_KEY_NAME, b64uEncode(key), KEY_OPTIONS);
  return key;
}

// One key lookup at a time, so two saves at once can't each make (and keep) their own key.
let keyInFlight: Promise<Uint8Array> | null = null;

function keyForSaving(): Promise<Uint8Array> {
  keyInFlight ??= makeOrReadKey().finally(() => {
    keyInFlight = null;
  });
  return keyInFlight;
}

function freshNonce(): Uint8Array {
  try {
    return randomBytes(nacl.secretbox.nonceLength);
  } catch {
    throw new Error('No secure random source: nothing is saved.');
  }
}

/** Seal `text` for AsyncStorage. Throws (and nothing should be saved) without a secure random source. */
export async function sealForDisk(text: string): Promise<string> {
  const key = await keyForSaving();
  const nonce = freshNonce();
  const box = nacl.secretbox(decodeUTF8(text), nonce, key);
  return JSON.stringify({ v: 1, n: b64uEncode(nonce), c: b64uEncode(box) });
}

/** Seal bytes for a file (a receipt photo): the 24-byte nonce, then the box. Throws like `sealForDisk`. */
export async function sealBytesForDisk(plain: Uint8Array): Promise<Uint8Array> {
  const key = await keyForSaving();
  const nonce = freshNonce();
  const box = nacl.secretbox(plain, nonce, key);
  const out = new Uint8Array(nonce.length + box.length);
  out.set(nonce);
  out.set(box, nonce.length);
  return out;
}

/** The bytes sealed by `sealBytesForDisk`, or null if they can't be opened on this phone. Never throws. */
export async function openBytesFromDisk(sealed: Uint8Array): Promise<Uint8Array | null> {
  try {
    const n = nacl.secretbox.nonceLength;
    if (sealed.length < n + nacl.secretbox.overheadLength) return null;
    const key = await readKey();
    return key ? nacl.secretbox.open(sealed.subarray(n), sealed.subarray(0, n), key) : null;
  } catch {
    return null;
  }
}

/** The text sealed by `sealForDisk`, or null if it can't be opened on this phone. Never throws. */
export async function openFromDisk(stored: string): Promise<string | null> {
  try {
    const parsed = JSON.parse(stored) as { v?: unknown; n?: unknown; c?: unknown };
    if (parsed?.v !== 1 || typeof parsed.n !== 'string' || typeof parsed.c !== 'string') return null;
    const key = await readKey();
    if (!key) return null;
    const opened = nacl.secretbox.open(b64uDecode(parsed.c), b64uDecode(parsed.n, nacl.secretbox.nonceLength), key);
    return opened ? encodeUTF8(opened) : null;
  } catch {
    return null;
  }
}
