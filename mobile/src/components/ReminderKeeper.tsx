import { useEffect } from 'react';

import { sweepPhotoCaches } from '@/receipts/photo';
import { cleanUpPhotos } from '@/receipts/receiptQueue';
import { rescheduleReminders } from '@/sync/reminders';
import { useSnapshot } from '@/sync/store';

/**
 * At app start, once the saved snapshot is read and the first screen is drawn: reminders made fresh
 * (contract §9), photo files no queued receipt lists cleaned up, and any plain photo the camera left
 * behind deleted.
 */
export function ReminderKeeper() {
  const { loading, lastSyncedAt, snapshot, isSample } = useSnapshot();
  useEffect(() => {
    if (loading) return;
    const task = requestIdleCallback(() => {
      void (async () => {
        sweepPhotoCaches();
        const waitingReceipts = await cleanUpPhotos(); // reads the queue once for both jobs
        await rescheduleReminders({
          lastSyncedAt,
          suggestedDays: isSample ? null : snapshot.settings.reminder_days_default,
          waitingReceipts,
        });
      })();
    }, { timeout: 3000 }); // idle, or at most 3 s later
    return () => cancelIdleCallback(task);
    // Once per start: syncs and Settings changes reschedule on their own.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);
  return null;
}
