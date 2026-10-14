/**
 * Sync reminders (roadmap #21, sync contract §9): local notifications so the budget on the phone doesn't
 * go stale. Nothing is sent anywhere: the phone schedules them for itself.
 *
 * - **Setting:** every 1, 2 or 3 days (`budgetbuddy.sync_reminder.v1`). Until you pick, the computer's
 *   `settings.reminder_days_default` is used (2 with no snapshot yet). Off is a phone-only extra choice.
 * - **When:** due = last sync + N days, moved out of quiet hours (21:00-09:00, to 09:00); if that's past,
 *   the next non-quiet minute at least a minute from now. Two follow-ups 1 and 2 days later, then none.
 * - **Rescheduled** after every successful sync, when the setting changes, and when the app starts;
 *   each time all three are cancelled and made fresh. Not paired: none.
 * - **Permission** is asked right after the first successful sync, with a line of explanation
 *   (`SyncPanel`), or when you pick a choice in Settings. Refused: no reminders.
 * - **Text** never includes money: "Time to sync Budget Buddy", and how many receipts are waiting.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { loadCredentials } from './credentials';

export type ReminderChoice = 0 | 1 | 2 | 3; // 0 = off
export const REMINDER_CHOICES: readonly ReminderChoice[] = [1, 2, 3, 0];
export const REMINDER_PREF_KEY = 'budgetbuddy.sync_reminder.v1';
export const PERMISSION_ASKED_KEY = 'budgetbuddy.reminder_permission_asked.v1';
export const REMINDER_IDS = [0, 1, 2].map((i) => `budgetbuddy-sync-reminder-${i}`);
export const REMINDER_TITLE = 'Time to sync Budget Buddy';
export const PERMISSION_DENIED_MESSAGE =
  "Reminders are off because this phone doesn't allow Budget Buddy to show notifications. You can allow them in your phone's settings.";
export const SAVE_CHOICE_FAILED = "Couldn't save your reminder choice on this phone. Please try again.";
const DEFAULT_DAYS = 2;
const QUIET_FROM = 21; // 21:00
const QUIET_UNTIL = 9; // 09:00
const CHANNEL_ID = 'sync-reminders';
const MINUTE_MS = 60 * 1000;
const DAY_MS = 24 * 60 * MINUTE_MS;

/** "Every day", "Every 2 days", "Every 3 days", "Off". */
export function reminderLabel(days: ReminderChoice): string {
  if (days === 0) return 'Off';
  return days === 1 ? 'Every day' : `Every ${days} days`;
}

/** The reminder's text: how many receipts are waiting, if any; never money. */
export function reminderBody(waitingReceipts = 0): string {
  const home = "When you're home, open the app and tap Sync.";
  if (waitingReceipts <= 0) return home;
  return `You have ${waitingReceipts} ${waitingReceipts === 1 ? 'receipt' : 'receipts'} waiting. ${home}`;
}

/** `at`, or 09:00 the next morning (or that morning) when `at` is in quiet hours, phone's local time. */
export function outOfQuietHours(at: Date): Date {
  const hour = at.getHours();
  if (hour >= QUIET_UNTIL && hour < QUIET_FROM) return at;
  const morning = new Date(at);
  if (hour >= QUIET_FROM) morning.setDate(morning.getDate() + 1);
  morning.setHours(QUIET_UNTIL, 0, 0, 0);
  return morning;
}

/** The reminder and its two follow-ups for a sync at `lastSync` (contract §9). */
export function reminderTimes(lastSync: Date, days: 1 | 2 | 3, now: Date): Date[] {
  let due = outOfQuietHours(new Date(lastSync.getTime() + days * DAY_MS));
  const soonest = now.getTime() + MINUTE_MS;
  if (due.getTime() < soonest) due = outOfQuietHours(new Date(Math.ceil(soonest / MINUTE_MS) * MINUTE_MS));
  return [due, ...[1, 2].map((d) => outOfQuietHours(new Date(due.getTime() + d * DAY_MS)))];
}

/** Your choice, or null if you haven't picked one (then the computer's suggestion is used). */
export async function loadReminderChoice(): Promise<ReminderChoice | null> {
  try {
    const saved = await AsyncStorage.getItem(REMINDER_PREF_KEY);
    if (saved === null) return null;
    const n = Number(saved);
    return (REMINDER_CHOICES as readonly number[]).includes(n) ? (n as ReminderChoice) : null;
  } catch {
    return null;
  }
}

/** The days actually used: your choice, else the computer's suggestion, else 2. */
export function effectiveDays(choice: ReminderChoice | null, suggested: number | null): ReminderChoice {
  if (choice !== null) return choice;
  return suggested === 1 || suggested === 2 || suggested === 3 ? suggested : DEFAULT_DAYS;
}

export type ReminderContext = {
  lastSyncedAt: string | null;
  suggestedDays: number | null; // the snapshot's reminder_days_default (null while showing sample data)
  waitingReceipts?: number;
  now?: Date;
};

async function cancelAll(): Promise<void> {
  for (const id of REMINDER_IDS) await Notifications.cancelScheduledNotificationAsync(id);
}

/** Cancel the reminders and schedule fresh ones (contract §9). Never asks for permission; never throws. */
export async function rescheduleReminders(ctx: ReminderContext): Promise<void> {
  try {
    await cancelAll();
    if (!(await loadCredentials())) return; // not paired: no reminders
    const days = effectiveDays(await loadReminderChoice(), ctx.suggestedDays);
    if (days === 0 || !(await Notifications.getPermissionsAsync()).granted) return;
    const now = ctx.now ?? new Date();
    const lastSync = ctx.lastSyncedAt ? new Date(ctx.lastSyncedAt) : now;
    if (Number.isNaN(lastSync.getTime())) return;
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync(CHANNEL_ID, {
        name: 'Sync reminders',
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }
    const content = { title: REMINDER_TITLE, body: reminderBody(ctx.waitingReceipts) };
    const times = reminderTimes(lastSync, days, now);
    for (let i = 0; i < times.length; i++) {
      await Notifications.scheduleNotificationAsync({
        identifier: REMINDER_IDS[i],
        content,
        trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: times[i], channelId: CHANNEL_ID },
      });
    }
  } catch {
    // No reminders this time; the next sync or app start tries again.
  }
}

async function askPermission(): Promise<boolean> {
  try {
    await AsyncStorage.setItem(PERMISSION_ASKED_KEY, '1');
    if ((await Notifications.getPermissionsAsync()).granted) return true;
    // Only what a reminder uses: no badge.
    const asked = await Notifications.requestPermissionsAsync({
      ios: { allowAlert: true, allowBadge: false, allowSound: true },
    });
    return asked.granted;
  } catch {
    return false;
  }
}

/** After a successful sync: true if the phone should offer reminders (never asked, not off, not allowed yet). */
export async function shouldOfferReminders(): Promise<boolean> {
  try {
    if ((await AsyncStorage.getItem(PERMISSION_ASKED_KEY)) !== null) return false;
    if ((await loadReminderChoice()) === 0) return false;
    return !(await Notifications.getPermissionsAsync()).granted;
  } catch {
    return false;
  }
}

/** You answered the offer after a sync: "Allow" asks the phone; "Not now" only stops asking. */
export async function answerReminderOffer(allow: boolean, ctx: ReminderContext): Promise<string | null> {
  if (!allow) {
    await AsyncStorage.setItem(PERMISSION_ASKED_KEY, '1').catch(() => undefined);
    return null;
  }
  const granted = await askPermission();
  await rescheduleReminders(ctx);
  return granted ? null : PERMISSION_DENIED_MESSAGE;
}

/** Save your choice in Settings and reschedule. Picking a number asks for permission if needed. */
export async function chooseReminderDays(choice: ReminderChoice, ctx: ReminderContext): Promise<string | null> {
  try {
    await AsyncStorage.setItem(REMINDER_PREF_KEY, String(choice));
  } catch {
    return SAVE_CHOICE_FAILED;
  }
  const granted = choice === 0 || (await askPermission());
  await rescheduleReminders(ctx);
  return granted ? null : PERMISSION_DENIED_MESSAGE;
}
