import { useEffect } from 'react';

import { cleanUpPhotos, waitingCount } from '@/receipts/receiptQueue';
import { rescheduleReminders } from '@/sync/reminders';
import { useSnapshot } from '@/sync/store';

/**
 * At app start, once the saved snapshot is read: reminders made fresh (contract §9), and photo files no
 * queued receipt lists cleaned up.
 */
export function ReminderKeeper() {
  const { loading, lastSyncedAt, snapshot, isSample } = useSnapshot();
  useEffect(() => {
    if (loading) return;
    void (async () => {
      await cleanUpPhotos();
      await rescheduleReminders({
        lastSyncedAt,
        suggestedDays: isSample ? null : snapshot.settings.reminder_days_default,
        waitingReceipts: await waitingCount(),
      });
    })();
    // Once per start: syncs and Settings changes reschedule on their own.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);
  return null;
}
