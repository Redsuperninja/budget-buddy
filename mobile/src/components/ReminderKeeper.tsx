import { useEffect } from 'react';

import { rescheduleReminders } from '@/sync/reminders';
import { useSnapshot } from '@/sync/store';

/** Contract §9: reminders are made fresh when the app starts (once the saved snapshot is read). */
export function ReminderKeeper() {
  const { loading, lastSyncedAt, snapshot, isSample } = useSnapshot();
  useEffect(() => {
    if (loading) return;
    void rescheduleReminders({ lastSyncedAt, suggestedDays: isSample ? null : snapshot.settings.reminder_days_default });
    // Once per start: syncs and Settings changes reschedule on their own.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);
  return null;
}
