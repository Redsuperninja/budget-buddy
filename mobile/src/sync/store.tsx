/**
 * A tiny snapshot store (React context).
 *
 * On start it loads the last saved snapshot from the phone's local storage. If there isn't one
 * (never synced) or it can't be read, it falls back to the made-up sample snapshot so the app
 * still has something to show.
 *
 * Storage note: the cached snapshot is FINANCIAL DATA (budget, recent transactions, balances).
 * It contains no keys or tokens, so it lives in AsyncStorage rather than expo-secure-store
 * (which is for small secrets and has size limits). It is protected by the phone's own OS lock
 * and app sandbox. Encrypting this cache at rest is a possible follow-up.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { SAMPLE_SNAPSHOT } from './sampleSnapshot';
import { parseSnapshot, SNAPSHOT_INVALID_MESSAGE, SNAPSHOT_LIMITS } from './snapshot';
import type { Snapshot } from './snapshot';

export const SNAPSHOT_STORAGE_KEY = 'budgetbuddy.snapshot.v1';

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
  let raw: string | null;
  try {
    raw = await AsyncStorage.getItem(SNAPSHOT_STORAGE_KEY);
  } catch {
    return { ...SAMPLE_STATE, loading: false, loadError: SNAPSHOT_INVALID_MESSAGE };
  }
  if (raw === null) return { ...SAMPLE_STATE, loading: false };
  // Far bigger than any real snapshot: damaged, so not even read (it could freeze the screen).
  if (raw.length > SNAPSHOT_LIMITS.storedChars) {
    return { ...SAMPLE_STATE, loading: false, loadError: SNAPSHOT_INVALID_MESSAGE };
  }

  try {
    const stored = JSON.parse(raw) as Partial<StoredSnapshot> | null;
    const result = parseSnapshot(stored?.snapshot);
    const syncedAt = typeof stored?.last_synced_at === 'string' ? stored.last_synced_at : null;
    if (result.ok && syncedAt !== null && !Number.isNaN(Date.parse(syncedAt))) {
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
      await AsyncStorage.setItem(SNAPSHOT_STORAGE_KEY, text);
    } catch {
      return "Couldn't save your budget on this phone. Check that your phone has free space, then try again.";
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
