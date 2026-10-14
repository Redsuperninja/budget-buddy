/** Add Receipt: photo, details, then waiting on the phone, encrypted (roadmap #20). Made-up data only. */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import * as FileSystem from 'expo-file-system';
import type { ReactNode } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import AddReceiptScreen, { SAVED_TEXT } from '@/app/add-receipt';
import { WAITING_TEXT } from '@/components/receipts/WaitingReceipts';
import { listReceipts } from '@/receipts/receiptQueue';
import { SnapshotProvider } from '@/sync/store';

const files = (FileSystem as unknown as { __files: Map<string, Uint8Array> }).__files;
const CAMERA_URI = 'file://camera/shot.jpg';
const RESIZED_URI = 'file://cache/resized.jpg';
const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 9, 9, 9, 9]);

jest.mock('expo-router', () => ({
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, []),
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('expo-camera', () => {
  const React = require('react');
  const CameraView = React.forwardRef((_props: unknown, ref: unknown) => {
    React.useImperativeHandle(ref, () => ({
      takePictureAsync: async () => {
        // The camera writes a plain JPEG to disk, like the real one.
        require('expo-file-system').__files.set('file://camera/shot.jpg', new Uint8Array([0xff, 0xd8, 0xff, 1]));
        return { uri: 'file://camera/shot.jpg', width: 3024, height: 4032 };
      },
    }));
    return null;
  });
  return { CameraView, useCameraPermissions: () => [{ granted: true }, jest.fn()] };
});

jest.mock('expo-image-manipulator', () => ({
  SaveFormat: { JPEG: 'jpeg' },
  ImageManipulator: {
    manipulate: () => ({
      resize: jest.fn(),
      renderAsync: async () => ({
        saveAsync: async () => {
          require('expo-file-system').__files.set('file://cache/resized.jpg', new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 9, 9, 9, 9]));
          return { uri: 'file://cache/resized.jpg', width: 1200, height: 1600 };
        },
      }),
    }),
  },
}));

jest.setTimeout(30_000); // the first render of a screen is slow on a cold cache

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } };
function Wrapper({ children }: { children: ReactNode }) {
  return (
    <SafeAreaProvider initialMetrics={metrics}>
      <SnapshotProvider>{children}</SnapshotProvider>
    </SafeAreaProvider>
  );
}

beforeEach(async () => {
  await AsyncStorage.clear();
  files.clear();
});

describe('Add a receipt', () => {
  it('takes a photo, saves what you typed, and keeps it waiting, encrypted', async () => {
    await render(<AddReceiptScreen />, { wrapper: Wrapper });
    await fireEvent.press(await screen.findByText('Take photo'));
    await fireEvent.press(await screen.findByText('Take photo')); // the camera's shutter
    expect(await screen.findByText('About this receipt')).toBeTruthy();

    await fireEvent.changeText(screen.getByLabelText('Store'), 'Fake Corner Pharmacy');
    await fireEvent.changeText(screen.getByLabelText('Total'), '23.99');
    await fireEvent.press(screen.getByText('Save receipt'));

    expect(await screen.findByText(SAVED_TEXT)).toBeTruthy();
    expect(screen.getByText('1 receipt waiting')).toBeTruthy();
    expect(screen.getByText(WAITING_TEXT)).toBeTruthy();
    const [queued] = await listReceipts();
    expect(queued).toMatchObject({ merchant: 'Fake Corner Pharmacy', total_cents: 2399, width: 1200, height: 1600 });
    expect(queued.photo_bytes).toBe(JPEG.length);

    // The camera's and the resized plain files are gone; only the sealed photo remains.
    expect(files.has(CAMERA_URI)).toBe(false);
    expect(files.has(RESIZED_URI)).toBe(false);
    const [sealed] = [...files.values()];
    expect([...sealed.subarray(0, 3)]).not.toEqual([0xff, 0xd8, 0xff]);
  });

  it('says what is wrong with a total it cannot read', async () => {
    await render(<AddReceiptScreen />, { wrapper: Wrapper });
    await fireEvent.press(await screen.findByText('Take photo'));
    await fireEvent.press(await screen.findByText('Take photo'));
    await fireEvent.changeText(await screen.findByLabelText('Total'), 'twelve');
    await fireEvent.press(screen.getByText('Save receipt'));
    expect(await screen.findByText('Enter the total as an amount, like 23.99, or leave it empty.')).toBeTruthy();
    expect(await listReceipts()).toEqual([]);
  });

  it('deletes a waiting receipt', async () => {
    await render(<AddReceiptScreen />, { wrapper: Wrapper });
    await fireEvent.press(await screen.findByText('Take photo'));
    await fireEvent.press(await screen.findByText('Take photo'));
    await fireEvent.press(await screen.findByText('Save receipt'));
    await fireEvent.press(await screen.findByText('Delete Receipt'));
    await waitFor(async () => expect(await listReceipts()).toEqual([]));
    expect(files.size).toBe(0);
  });
});
