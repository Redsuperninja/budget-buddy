/**
 * "Do one sync" for screens: loads the saved credentials, runs the sync client, and turns every outcome
 * into plain English. Only one sync runs at a time; a second tap while one is running joins it.
 */

import { waitingCount } from '@/receipts/receiptQueue';
import { uploadReceipts } from '@/receipts/receiptUpload';

import { loadCredentials } from './credentials';
import { rescheduleReminders } from './reminders';
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
      const { snapshot } = await syncNow(creds, { save, uploadReceipts });
      // Contract §9: fresh reminders, counted from this sync.
      await rescheduleReminders({
        lastSyncedAt: new Date().toISOString(),
        suggestedDays: snapshot.settings.reminder_days_default,
        waitingReceipts: await waitingCount(),
      });
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
