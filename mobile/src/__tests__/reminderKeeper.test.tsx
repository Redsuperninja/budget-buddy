import { render } from '@testing-library/react-native';

import { ReminderKeeper } from '@/components/ReminderKeeper';

const calls: string[] = [];

jest.mock('@/receipts/photo', () => ({ sweepPhotoCaches: () => void calls.push('sweep') }));
jest.mock('@/receipts/receiptQueue', () => ({
  cleanUpPhotos: async () => {
    calls.push('cleanUp');
    return 2;
  },
}));
jest.mock('@/sync/reminders', () => ({
  rescheduleReminders: async (o: { waitingReceipts: number }) => void calls.push(`reschedule:${o.waitingReceipts}`),
}));
jest.mock('@/sync/store', () => ({
  useSnapshot: () => ({
    loading: false,
    lastSyncedAt: null,
    isSample: true,
    snapshot: { settings: { reminder_days_default: 2 } },
  }),
}));

describe('ReminderKeeper', () => {
  it('sweeps camera leftovers at once, and cleans up and reschedules after the first screen', async () => {
    const idle: Array<() => void> = [];
    (globalThis as unknown as { requestIdleCallback: unknown }).requestIdleCallback = (cb: () => void) => idle.push(cb);
    calls.length = 0;

    await render(<ReminderKeeper />);
    expect(calls).toEqual(['sweep']); // nothing else until the phone is idle

    idle[0]();
    await new Promise((r) => setTimeout(r, 0));
    expect(calls).toEqual(['sweep', 'cleanUp', 'reschedule:2']); // one queue read feeds the reminder
  });
});
