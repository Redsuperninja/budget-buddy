/** Sync reminders (roadmap #21, sync contract §9). Times are the phone's local time. */
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';

import { saveCredentials } from '../credentials';
import {
  answerReminderOffer,
  chooseReminderDays,
  effectiveDays,
  loadReminderChoice,
  outOfQuietHours,
  PERMISSION_DENIED_MESSAGE,
  reminderBody,
  REMINDER_IDS,
  REMINDER_TITLE,
  reminderLabel,
  reminderTimes,
  rescheduleReminders,
  shouldOfferReminders,
} from '../reminders';

const mock = Notifications as unknown as { __scheduled: Map<string, any>; __permission: { granted: boolean } };
const CREDS = {
  host: '192.168.1.20', port: 8765, sync_key: '4OHi4-Tl5ufo6err7O3u7_Dx8vP09fb3-Pn6-_z9_v8',
  token: 'YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8', server_id: 'Zk3pR7tQ1xYb9mWc2nLs5Q', server_name: 'Home Base', device_id: 3,
};
const at = (d: number, h: number, m = 0) => new Date(2026, 9, d, h, m); // October 2026, local time
const times = () => REMINDER_IDS.map((id) => mock.__scheduled.get(id)?.trigger.date as Date | undefined);

beforeEach(async () => {
  await AsyncStorage.clear();
  await SecureStore.deleteItemAsync('budgetbuddy.credentials.v1');
  mock.__scheduled.clear();
  mock.__permission.granted = true;
  await saveCredentials(CREDS);
});

describe('when reminders go off', () => {
  it('is N days after the last sync, then 1 and 2 days later', () => {
    expect(reminderTimes(at(10, 14), 2, at(10, 14))).toEqual([at(12, 14), at(13, 14), at(14, 14)]);
  });

  it('never in quiet hours (21:00-09:00): moved to 09:00', () => {
    expect(outOfQuietHours(at(12, 22, 30))).toEqual(at(13, 9));
    expect(outOfQuietHours(at(12, 6))).toEqual(at(12, 9));
    expect(outOfQuietHours(at(12, 20, 59))).toEqual(at(12, 20, 59));
    expect(reminderTimes(at(10, 23), 1, at(10, 23))[0]).toEqual(at(12, 9));
  });

  it('is the next non-quiet minute when it is already overdue', () => {
    expect(reminderTimes(at(1, 12), 1, at(10, 14, 0))[0]).toEqual(at(10, 14, 1));
    expect(reminderTimes(at(1, 12), 1, at(10, 22))[0]).toEqual(at(11, 9));
  });
});

describe('rescheduling', () => {
  it("uses the computer's suggestion until you pick, and the contract's words", async () => {
    await rescheduleReminders({ lastSyncedAt: at(10, 14).toISOString(), suggestedDays: 3, waitingReceipts: 2, now: at(10, 14) });
    expect(times()).toEqual([at(13, 14), at(14, 14), at(15, 14)]);
    const content = mock.__scheduled.get(REMINDER_IDS[0]).content;
    expect(content).toEqual({
      title: REMINDER_TITLE,
      body: "You have 2 receipts waiting. When you're home, open the app and tap Sync.",
    });
    expect(reminderBody()).toBe("When you're home, open the app and tap Sync.");
    expect(effectiveDays(null, null)).toBe(2);
  });

  it('makes none when the phone is not paired, reminders are off, or not allowed', async () => {
    const ctx = { lastSyncedAt: at(10, 14).toISOString(), suggestedDays: 2, now: at(10, 14) };
    await SecureStore.deleteItemAsync('budgetbuddy.credentials.v1');
    await rescheduleReminders(ctx);
    expect(mock.__scheduled.size).toBe(0);
    await saveCredentials(CREDS);
    await chooseReminderDays(0, ctx);
    expect(mock.__scheduled.size).toBe(0);
    await chooseReminderDays(1, ctx);
    expect(mock.__scheduled.size).toBe(3);
    mock.__permission.granted = false;
    await rescheduleReminders(ctx);
    expect(mock.__scheduled.size).toBe(0);
  });

  it('replaces the old reminders each time', async () => {
    await rescheduleReminders({ lastSyncedAt: at(10, 14).toISOString(), suggestedDays: 1, now: at(10, 14) });
    await rescheduleReminders({ lastSyncedAt: at(11, 15).toISOString(), suggestedDays: 1, now: at(11, 15) });
    expect(times()).toEqual([at(12, 15), at(13, 15), at(14, 15)]);
  });
});

describe('asking', () => {
  it('offers once after the first sync; Not now stops asking', async () => {
    mock.__permission.granted = false;
    expect(await shouldOfferReminders()).toBe(true);
    expect(await answerReminderOffer(false, { lastSyncedAt: null, suggestedDays: 2 })).toBeNull();
    expect(await shouldOfferReminders()).toBe(false);
  });

  it('says plainly when the phone refuses', async () => {
    mock.__permission.granted = false;
    const ctx = { lastSyncedAt: null, suggestedDays: 2 };
    expect(await answerReminderOffer(true, ctx)).toBe(PERMISSION_DENIED_MESSAGE);
    expect(await chooseReminderDays(2, ctx)).toBe(PERMISSION_DENIED_MESSAGE);
    expect(await loadReminderChoice()).toBe(2); // kept: used once you allow notifications
  });

  it('does not offer when reminders are off or already allowed', async () => {
    expect(await shouldOfferReminders()).toBe(false); // allowed
    mock.__permission.granted = false;
    await chooseReminderDays(0, { lastSyncedAt: null, suggestedDays: 2 });
    await AsyncStorage.removeItem('budgetbuddy.reminder_permission_asked.v1');
    expect(await shouldOfferReminders()).toBe(false);
  });

  it('has plain labels', () => {
    expect(([1, 2, 3, 0] as const).map(reminderLabel)).toEqual(['Every day', 'Every 2 days', 'Every 3 days', 'Off']);
  });
});
