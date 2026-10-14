/** The saved snapshot is always encrypted on the phone (issue #19). Made-up data only. */
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';

import { CACHE_KEY_NAME } from '../cacheCrypto';
import { SAMPLE_SNAPSHOT } from '../sampleSnapshot';
import { SNAPSHOT_INVALID_MESSAGE } from '../snapshot';
import { LEGACY_SNAPSHOT_KEY, readSaved, SNAPSHOT_STORAGE_KEY, writeSaved } from '../snapshotDisk';
import { loadStoredSnapshot } from '../store';
import * as transport from '../transport';

const DESCRIPTION = 'Fake Lakeside Bakery';

function savedText(): string {
  const copy = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
  copy.transactions[0].description = DESCRIPTION;
  return JSON.stringify({ snapshot: copy, last_synced_at: new Date().toISOString() });
}

beforeEach(async () => {
  await AsyncStorage.clear();
  await SecureStore.deleteItemAsync(CACHE_KEY_NAME);
  jest.restoreAllMocks();
});

describe('encrypted snapshot on the phone', () => {
  it('keeps no readable financial data on disk, and reads it back', async () => {
    await writeSaved(savedText());
    const raw = (await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY)) as string;
    expect(raw).not.toContain(DESCRIPTION);
    expect(raw).not.toContain('amount_cents');
    expect(JSON.parse(raw)).toEqual({ v: 1, n: expect.any(String), c: expect.any(String) });
    expect(await readSaved()).toMatchObject({ kind: 'text', legacy: false });
    const state = await loadStoredSnapshot();
    expect(state.isSample).toBe(false);
    expect(state.snapshot.transactions[0].description).toBe(DESCRIPTION);
  });

  it('uses a fresh nonce on every save', async () => {
    await writeSaved(savedText());
    const first = JSON.parse((await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY)) as string).n;
    await writeSaved(savedText());
    const second = JSON.parse((await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY)) as string).n;
    expect(second).not.toBe(first);
  });

  it.each([
    ['a damaged box', (s: any) => ({ ...s, c: s.c.slice(0, -4) + 'AAAA' })],
    ['a wrong nonce length', (s: any) => ({ ...s, n: s.n.slice(0, 10) })],
    ['another version', (s: any) => ({ ...s, v: 2 })],
  ])('treats %s as nothing saved, with the friendly message', async (_name, damage) => {
    await writeSaved(savedText());
    const sealed = JSON.parse((await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY)) as string);
    await AsyncStorage.setItem(SNAPSHOT_STORAGE_KEY, JSON.stringify(damage(sealed)));
    const state = await loadStoredSnapshot();
    expect(state.isSample).toBe(true);
    expect(state.loadError).toBe(SNAPSHOT_INVALID_MESSAGE);
  });

  it('treats a missing key (a restored backup) as nothing saved', async () => {
    await writeSaved(savedText());
    await SecureStore.deleteItemAsync(CACHE_KEY_NAME);
    expect(await readSaved()).toEqual({ kind: 'unreadable' });
  });

  it('seals a plain copy from before encryption and deletes it', async () => {
    await AsyncStorage.setItem(LEGACY_SNAPSHOT_KEY, savedText());
    const state = await loadStoredSnapshot();
    expect(state.snapshot.transactions[0].description).toBe(DESCRIPTION);
    expect(await AsyncStorage.getItem(LEGACY_SNAPSHOT_KEY)).toBeNull();
    expect(await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY)).not.toContain(DESCRIPTION);
  });

  it('keeps one key and the newest copy when two saves run at once', async () => {
    const older = savedText().replace(DESCRIPTION, 'Fake Older Shop');
    await Promise.all([writeSaved(older), writeSaved(savedText())]);
    const state = await loadStoredSnapshot();
    expect(state.snapshot.transactions[0].description).toBe(DESCRIPTION);
  });

  it('deletes a plain copy from before encryption even when it is unusable', async () => {
    await AsyncStorage.setItem(LEGACY_SNAPSHOT_KEY, JSON.stringify({ snapshot: { contract: 1 }, last_synced_at: 'x' }));
    const state = await loadStoredSnapshot();
    expect(state.loadError).toBe(SNAPSHOT_INVALID_MESSAGE);
    expect(await AsyncStorage.getItem(LEGACY_SNAPSHOT_KEY)).toBeNull();
  });

  it('deletes the plain copy even if sealing it fails', async () => {
    await AsyncStorage.setItem(LEGACY_SNAPSHOT_KEY, savedText());
    jest.spyOn(transport, 'randomBytes').mockImplementation(() => {
      throw new Error('no secure random');
    });
    const state = await loadStoredSnapshot();
    expect(state.snapshot.transactions[0].description).toBe(DESCRIPTION); // shown this time
    expect(await AsyncStorage.getItem(LEGACY_SNAPSHOT_KEY)).toBeNull();
    expect(await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY)).toBeNull(); // nothing plain or sealed left
  });

  it('saves nothing without a secure random source', async () => {
    jest.spyOn(transport, 'randomBytes').mockImplementation(() => {
      throw new Error('no secure random');
    });
    await expect(writeSaved(savedText())).rejects.toThrow();
    expect(await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY)).toBeNull();
  });
});
