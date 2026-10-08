/**
 * "Do one sync" for screens: loads the saved credentials, runs the sync client, and turns every outcome
 * into plain English. Only one sync runs at a time; a second tap while one is running joins it.
 */
import Constants from 'expo-constants';

import { loadCredentials } from './credentials';
import { PAIR_MESSAGES, PairError, NEEDS_ATTENTION_CODES } from './pairErrors';
import type { PairErrorCode } from './pairErrors';
import type { Snapshot } from './snapshot';
import { syncNow } from './syncClient';

export const NOT_CONNECTED_MESSAGE =
  'Your phone is not connected to your computer yet. Go to Settings, then tap Connect to your computer.';

export type SyncOutcome =
  | { ok: true }
  | { ok: false; message: string; code: PairErrorCode | 'not_connected'; needsAttention: boolean };

let inFlight: Promise<SyncOutcome> | null = null;

export function runSync(save: (snapshot: Snapshot) => Promise<string | null>): Promise<SyncOutcome> {
  if (inFlight) return inFlight;
  const job = (async (): Promise<SyncOutcome> => {
    try {
      const creds = await loadCredentials();
      if (!creds) return { ok: false, message: NOT_CONNECTED_MESSAGE, code: 'not_connected', needsAttention: false };
      await syncNow(creds, { save, appVersion: Constants.expoConfig?.version ?? '1.0.0' });
      return { ok: true };
    } catch (e) {
      const err = e instanceof PairError ? e : new PairError('something_wrong');
      return {
        ok: false,
        message: PAIR_MESSAGES[err.code],
        code: err.code,
        needsAttention: NEEDS_ATTENTION_CODES.includes(err.code),
      };
    }
  })();
  inFlight = job;
  void job.finally(() => {
    inFlight = null;
  });
  return job;
}
