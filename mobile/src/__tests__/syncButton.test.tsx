import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import HomeScreen from '@/app/index';
import SettingsScreen from '@/app/settings';
import { SAMPLE_BANNER_TEXT } from '@/components/SnapshotNotices';
import { SYNCED_TEXT, SYNCING_TEXT } from '@/components/SyncPanel';
import { REMINDERS_TITLE } from '@/components/SyncReminders';
import { REMINDER_OFFER_TEXT } from '@/components/ReminderOffer';
import * as Notifications from 'expo-notifications';
import { REMINDER_IDS } from '@/sync/reminders';
import { saveCredentials, setNeedsAttention } from '@/sync/credentials';
import { PAIR_MESSAGES } from '@/sync/pairErrors';
import { SAMPLE_SNAPSHOT } from '@/sync/sampleSnapshot';
import type { Snapshot } from '@/sync/snapshot';
import { SnapshotProvider } from '@/sync/store';

const mockRunSync = jest.fn();
jest.mock('@/sync/runSync', () => ({ runSync: (...a: unknown[]) => mockRunSync(...a) }));
const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, []),
}));

jest.setTimeout(30_000); // the first render of a screen is slow on a cold cache

const metrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 0, left: 0, right: 0, bottom: 0 },
};
function Wrapper({ children }: { children: ReactNode }) {
  return (
    <SafeAreaProvider initialMetrics={metrics}>
      <SnapshotProvider>{children}</SnapshotProvider>
    </SafeAreaProvider>
  );
}

const REAL: Snapshot = {
  ...JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT)),
  server_id: 'Zk3pR7tQ1xYb9mWc2nLs5Q',
};
REAL.transactions[0].description = 'Lakeside Bakery';

beforeEach(async () => {
  mockRunSync.mockReset();
  mockPush.mockReset();
  await AsyncStorage.clear();
  await setNeedsAttention(false);
});

describe('Sync now button', () => {
  it('shows sample data with the label until a sync works, then your real budget', async () => {
    mockRunSync.mockImplementation(async (save: (s: Snapshot) => Promise<string | null>) => {
      expect(await save(REAL)).toBeNull();
      return { ok: true };
    });
    await render(<HomeScreen />, { wrapper: Wrapper });
    expect(await screen.findByText(SAMPLE_BANNER_TEXT)).toBeTruthy();
    expect(SAMPLE_BANNER_TEXT).toMatch(/^Sample data/);
    expect(screen.getByText('Never synced')).toBeTruthy();

    await fireEvent.press(screen.getByText('Sync now'));

    expect(await screen.findByText(SYNCED_TEXT)).toBeTruthy();
    expect(screen.getByText('Lakeside Bakery')).toBeTruthy();
    expect(screen.queryByText(SAMPLE_BANNER_TEXT)).toBeNull();
    expect(screen.getByText('Last synced: Just now')).toBeTruthy();
  });

  it('shows Syncing... and disables the button while it works', async () => {
    let finish: (v: unknown) => void = () => undefined;
    mockRunSync.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    await render(<HomeScreen />, { wrapper: Wrapper });
    await fireEvent.press(await screen.findByText('Sync now'));

    expect(await screen.findByText(SYNCING_TEXT)).toBeTruthy();
    expect(screen.getByRole('button', { name: SYNCING_TEXT }).props.accessibilityState).toEqual(
      expect.objectContaining({ disabled: true }),
    );

    finish({ ok: true });
    expect(await screen.findByText(SYNCED_TEXT)).toBeTruthy();
    expect(screen.getByText('Sync now')).toBeTruthy();
  });

  it('shows a plain-English problem and keeps the old data when syncing fails', async () => {
    mockRunSync.mockResolvedValue({
      ok: false,
      message: PAIR_MESSAGES.server_unreachable,
      code: 'server_unreachable',
      needsAttention: false,
    });
    await render(<HomeScreen />, { wrapper: Wrapper });
    await fireEvent.press(await screen.findByText('Sync now'));

    expect(await screen.findByText(PAIR_MESSAGES.server_unreachable)).toBeTruthy();
    expect(screen.queryByText(SYNCED_TEXT)).toBeNull();
    expect(screen.getByText(SAMPLE_BANNER_TEXT)).toBeTruthy();
    expect(screen.queryByText('Pair again')).toBeNull();
  });

  it('offers Pair again when the computer says this phone was removed', async () => {
    mockRunSync.mockResolvedValue({
      ok: false,
      message: PAIR_MESSAGES.device_revoked,
      code: 'device_revoked',
      needsAttention: true,
    });
    await render(<HomeScreen />, { wrapper: Wrapper });
    await fireEvent.press(await screen.findByText('Sync now'));

    expect(await screen.findByText(PAIR_MESSAGES.device_revoked)).toBeTruthy();
    await fireEvent.press(screen.getByText('Pair again'));
    expect(mockPush).toHaveBeenCalledWith('/pair');
  });

  it('shows Pair again on start when an earlier sync flagged it', async () => {
    await setNeedsAttention(true);
    await render(<SettingsScreen />, { wrapper: Wrapper });
    await waitFor(() => expect(screen.getByText('Pair again')).toBeTruthy());
    expect(screen.getByText('Sync now')).toBeTruthy();
  });
});

describe('Sync reminders in Settings', () => {
  it('turns a reminder on from Settings', async () => {
    const scheduled = (Notifications as unknown as { __scheduled: Map<string, unknown> }).__scheduled;
    scheduled.clear();
    await saveCredentials({
      host: '192.168.1.20', port: 8765, sync_key: '4OHi4-Tl5ufo6err7O3u7_Dx8vP09fb3-Pn6-_z9_v8',
      token: 'YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8', server_id: 'Zk3pR7tQ1xYb9mWc2nLs5Q', server_name: 'Home Base', device_id: 3,
    }); // reminders only for a paired phone
    await render(<SettingsScreen />, { wrapper: Wrapper });
    expect(await screen.findByText(REMINDERS_TITLE)).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('radio', { name: 'Every 3 days' }).props.accessibilityState.disabled).toBe(false));
    await fireEvent.press(screen.getByText('Every 3 days'));
    await waitFor(() => expect(scheduled.has(REMINDER_IDS[0])).toBe(true));
    expect(screen.getByRole('radio', { name: 'Every 3 days' }).props.accessibilityState.checked).toBe(true);
  });
});

describe('Reminder offer after a sync', () => {
  const permission = (Notifications as unknown as { __permission: { granted: boolean } }).__permission;
  afterEach(() => {
    permission.granted = true;
  });

  it('offers reminders once, after the first successful sync', async () => {
    permission.granted = false;
    mockRunSync.mockImplementation(async (save: (s: Snapshot) => Promise<string | null>) => {
      await save(REAL);
      return { ok: true };
    });
    await render(<HomeScreen />, { wrapper: Wrapper });
    await fireEvent.press(await screen.findByText('Sync now'));
    expect(await screen.findByText(REMINDER_OFFER_TEXT)).toBeTruthy();

    await fireEvent.press(screen.getByText('Not now'));
    await waitFor(() => expect(screen.queryByText(REMINDER_OFFER_TEXT)).toBeNull());
    await fireEvent.press(screen.getByText('Sync now'));
    expect(await screen.findByText(SYNCED_TEXT)).toBeTruthy();
    expect(screen.queryByText(REMINDER_OFFER_TEXT)).toBeNull(); // asked once
  });
});
