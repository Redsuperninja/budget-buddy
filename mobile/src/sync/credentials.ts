/**
 * Pairing credentials live in expo-secure-store only (never AsyncStorage, never logs).
 * Saved as one item so old and new credentials can never get mixed.
 */
import * as SecureStore from 'expo-secure-store';

export const CREDENTIALS_KEY = 'budgetbuddy.credentials.v1';

export type Credentials = {
  host: string;
  port: number;
  sync_key: string; // base64url, 32 bytes
  token: string; // base64url, 32 bytes
  server_id: string;
  server_name: string;
  device_id: number;
};

/** Replaces any earlier credentials. Call only after a pairing fully succeeded. */
export async function saveCredentials(c: Credentials): Promise<void> {
  await SecureStore.setItemAsync(CREDENTIALS_KEY, JSON.stringify(c));
  await setNeedsAttention(false); // a fresh pairing clears the "Pair again" flag
}

// "Needs attention" (contract 7.2): set by a plaintext not_paired / device_revoked / decrypt_failed
// answer. It holds no secret. It only shows a "Pair again" button; nothing is deleted. A successful
// sync or a successful new pairing clears it.
export const NEEDS_ATTENTION_KEY = 'budgetbuddy.needsattention.v1';

export async function setNeedsAttention(on: boolean): Promise<void> {
  try {
    if (on) await SecureStore.setItemAsync(NEEDS_ATTENTION_KEY, '1');
    else await SecureStore.deleteItemAsync(NEEDS_ATTENTION_KEY);
  } catch {
    // The flag is only a hint; failing to store it must not break syncing.
  }
}

export async function getNeedsAttention(): Promise<boolean> {
  try {
    return (await SecureStore.getItemAsync(NEEDS_ATTENTION_KEY)) === '1';
  } catch {
    return false;
  }
}

export async function loadCredentials(): Promise<Credentials | null> {
  try {
    const text = await SecureStore.getItemAsync(CREDENTIALS_KEY);
    if (!text) return null;
    const c = JSON.parse(text) as Credentials;
    return typeof c.token === 'string' && typeof c.sync_key === 'string' ? c : null;
  } catch {
    return null;
  }
}
