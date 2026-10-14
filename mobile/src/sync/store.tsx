/**
 * A tiny snapshot store (React context).
 *
 * On start it loads the last saved snapshot from the phone's local storage. If there isn't one
 * (never synced) or it can't be read, it falls back to the made-up sample snapshot so the app
 * still has something to show.
 *
 * Storage note: the cached snapshot is FINANCIAL DATA (budget, recent transactions, balances).
 * It's too big for expo-secure-store, so it lives in AsyncStorage, which phones copy into cloud and
 * computer backups: it's always encrypted there with a key that stays on this phone
 * (`snapshotDisk.ts`, `cacheCrypto.ts`). Android app backup is off as well (app.json).
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { SAMPLE_SNAPSHOT } from './sampleSnapshot';
import { parseSnapshot, SNAPSHOT_INVALID_MESSAGE, SNAPSHOT_LIMITS } from './snapshot';
import type { Snapshot } from './snapshot';
import { readSaved, writeSaved } from './snapshotDisk';

export { LEGACY_SNAPSHOT_KEY, SNAPSHOT_STORAGE_KEY } from './snapshotDisk';

const SAVE_FAILED =
  "Couldn't save your budget on this phone. Unlock your phone and check it has free space, then try again.";

/** What we keep on disk: the snapshot plus when the phone last synced (phone clock, ISO UTC). */
type StoredSnapshot = { snapshot: unknown; last_synced_at: string };

export type SnapshotState = {
  /** The snapshot to show. Always present: the sample until a real one has been saved. */
  snapshot: Snapshot;
  /** When the phone last synced successfully (ISO date-time), or null if never. */
  lastSyncedAt: string | null;
  /** True while showing the made-up sample data. */
  isSample: boolean;
  /** True until the saved snapshot has been read from storage. */
  loading: boolean;
  /** A friendly message if the saved snapshot couldn't be read (we then show the sample). */
  loadError: string | null;
  /** Validate and save a fresh snapshot (used by sync). Returns an error message or null. */
  saveSnapshot: (raw: unknown, syncedAt?: Date) => Promise<string | null>;
};

type InternalState = Omit<SnapshotState, 'saveSnapshot'>;

const SAMPLE_STATE: InternalState = {
  snapshot: SAMPLE_SNAPSHOT,
  lastSyncedAt: null,
  isSample: true,
  loading: true,
  loadError: null,
};

const SnapshotContext = createContext<SnapshotState | null>(null);

/** Read and validate the cached snapshot. Never throws. */
export async function loadStoredSnapshot(): Promise<InternalState> {
  const saved = await readSaved();
  if (saved.kind === 'none') return { ...SAMPLE_STATE, loading: false };
  if (saved.kind === 'unreadable') return { ...SAMPLE_STATE, loading: false, loadError: SNAPSHOT_INVALID_MESSAGE };

  try {
    const stored = JSON.parse(saved.text) as Partial<StoredSnapshot> | null;
    const result = parseSnapshot(stored?.snapshot);
    const syncedAt = typeof stored?.last_synced_at === 'string' ? stored.last_synced_at : null;
    if (result.ok && syncedAt !== null && !Number.isNaN(Date.parse(syncedAt))) {
      if (saved.legacy) {
        // Saved before encryption: seal it now and drop the plain copy (best effort).
        await writeSaved(saved.text).catch(() => undefined);
      }
      return {
        snapshot: result.snapshot,
        lastSyncedAt: syncedAt,
        isSample: false,
        loading: false,
        loadError: null,
      };
    }
    const message = result.ok ? SNAPSHOT_INVALID_MESSAGE : result.message;
    return { ...SAMPLE_STATE, loading: false, loadError: message };
  } catch {
    return { ...SAMPLE_STATE, loading: false, loadError: SNAPSHOT_INVALID_MESSAGE };
  }
}

export function SnapshotProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<InternalState>(SAMPLE_STATE);

  useEffect(() => {
    let cancelled = false;
    loadStoredSnapshot().then((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const saveSnapshot = useCallback(async (raw: unknown, syncedAt: Date = new Date()) => {
    const result = parseSnapshot(raw);
    if (!result.ok) return result.message;
    const lastSyncedAt = syncedAt.toISOString();
    const stored: StoredSnapshot = { snapshot: result.snapshot, last_synced_at: lastSyncedAt };
    const text = JSON.stringify(stored);
    // Never save a copy the next start would refuse to read.
    if (text.length > SNAPSHOT_LIMITS.storedChars) return SNAPSHOT_INVALID_MESSAGE;
    try {
      await writeSaved(text); // sealed; nothing is saved without the phone's secure random source
    } catch {
      return SAVE_FAILED;
    }
    setState({
      snapshot: result.snapshot,
      lastSyncedAt,
      isSample: false,
      loading: false,
      loadError: null,
    });
    return null;
  }, []);

  const value = useMemo(() => ({ ...state, saveSnapshot }), [state, saveSnapshot]);
  return <SnapshotContext.Provider value={value}>{children}</SnapshotContext.Provider>;
}

/** Current snapshot and sync info. Must be used inside `SnapshotProvider`. */
export function useSnapshot(): SnapshotState {
  const ctx = useContext(SnapshotContext);
  if (!ctx) throw new Error('useSnapshot must be used inside <SnapshotProvider>');
  return ctx;
}
