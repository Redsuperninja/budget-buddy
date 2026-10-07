import { fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactNode } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import PairScreen, { DIFFERENT_COMPUTER_QUESTION } from '@/app/pair';
import { loadCredentials, saveCredentials } from '@/sync/credentials';
import SettingsScreen from '@/app/settings';
import { PAIR_MESSAGES } from '@/sync/pairErrors';
import { SnapshotProvider } from '@/sync/store';

jest.mock('expo-camera', () => ({
  CameraView: () => null,
  useCameraPermissions: () => [{ granted: true }, jest.fn()],
}));
jest.mock('expo-device', () => ({ deviceName: 'Test Phone', modelName: 'Test' }));
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
const Wrapper = ({ children }: { children: ReactNode }) => (
  <SafeAreaProvider initialMetrics={metrics}>
    <SnapshotProvider>{children}</SnapshotProvider>
  </SafeAreaProvider>
);

describe('Settings', () => {
  it('has a big button that opens the pair screen', async () => {
    await render(<SettingsScreen />, { wrapper: Wrapper });
    expect(await screen.findByText('Not connected to your computer yet')).toBeTruthy();
    await fireEvent.press(screen.getByText('Connect to your computer'));
    expect(mockPush).toHaveBeenCalledWith('/pair');
  });
});

describe('Pair screen', () => {
  it('tells the user what to do when the typed text is not a Budget Buddy code', async () => {
    await render(<PairScreen />, { wrapper: Wrapper });
    expect(screen.getByText(/home Wi-Fi/)).toBeTruthy();
    await fireEvent.press(screen.getByText('Type the code instead'));
    await fireEvent.changeText(screen.getByLabelText('Pairing code text'), 'hello');
    await fireEvent.press(screen.getByText('Connect'));
    expect(await screen.findByText(PAIR_MESSAGES.invalid_qr)).toBeTruthy();
  });

  it('asks first before replacing a connection with a different computer', async () => {
    const old = { host: '192.168.1.20', port: 8765, sync_key: 'k', token: 't', server_id: 'OLDOLDOLDOLDOLDOLDOLDQ', server_name: 'Old', device_id: 1 };
    await saveCredentials(old);
    const qr = {
      v: 1, app: 'budget-buddy', host: '192.168.1.21', port: 8765,
      code: 'pQ3mX9vT2aLk8RzN1bWc4g', pair_pub: 'YFpyXSpK3-6xop4X7dYhwbdZPujNvESsbEq24vgF0jw',
      server_id: 'Zk3pR7tQ1xYb9mWc2nLs5Q', name: 'New', exp: Math.floor(Date.now() / 1000) + 600,
    };
    const fetchSpy = jest.fn();
    (globalThis as { fetch: unknown }).fetch = fetchSpy;
    await render(<PairScreen />, { wrapper: Wrapper });
    await fireEvent.press(screen.getByText('Type the code instead'));
    await fireEvent.changeText(screen.getByLabelText('Pairing code text'), JSON.stringify(qr));
    await fireEvent.press(screen.getByText('Connect'));
    expect(await screen.findByText(DIFFERENT_COMPUTER_QUESTION)).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
    await fireEvent.press(screen.getByText('Cancel'));
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(await loadCredentials()).toEqual(old);
  });
});
