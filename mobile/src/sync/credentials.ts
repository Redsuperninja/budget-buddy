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
