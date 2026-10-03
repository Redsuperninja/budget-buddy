import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactNode } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import HomeScreen from '@/app/index';
import TaxesScreen from '@/app/taxes';
import { SAMPLE_BANNER_TEXT } from '@/components/SnapshotNotices';
import { SAMPLE_SNAPSHOT } from '@/sync/sampleSnapshot';
import { SNAPSHOT_INVALID_MESSAGE } from '@/sync/snapshot';
import { SNAPSHOT_STORAGE_KEY, SnapshotProvider } from '@/sync/store';

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

beforeEach(async () => {
  await AsyncStorage.clear();
});

describe('Home screen', () => {
  it('shows the sample data with a banner when never synced', async () => {
    await render(<HomeScreen />, { wrapper: Wrapper });

    expect(await screen.findByText(SAMPLE_BANNER_TEXT)).toBeTruthy();
    expect(screen.getByText('Never synced')).toBeTruthy();
    expect(screen.getByText('October 2026')).toBeTruthy();

    // Headline: 416,000 planned - 296,027 spent = 119,973 left.
    expect(screen.getByText('Left to spend')).toBeTruthy();
    expect(screen.getByText('$1,199.73')).toBeTruthy();
    expect(screen.getByText('12%')).toBeTruthy();

    // Groups with text status, not colour alone.
    expect(screen.getByText('Spent $2,256.80 of $2,600.00 (86%)')).toBeTruthy();
    expect(screen.getByText('Saved $600.00 of $1,040.00 (57%)')).toBeTruthy();
    expect(screen.getByText('$440.00 to go')).toBeTruthy();

    // Recent activity, money formatted.
    expect(screen.getByText('Recent activity')).toBeTruthy();
    expect(screen.getByText('-$14.75')).toBeTruthy();
    expect(screen.getAllByText('+$2,600.00').length).toBeGreaterThan(0);
  });

  it('labels Recent activity with neutral money in / money out wording', async () => {
    await render(<HomeScreen />, { wrapper: Wrapper });
    await screen.findByText(SAMPLE_BANNER_TEXT);

    expect(screen.getByLabelText(/^Move to Vacation fund, .*, Savings: Vacation fund\. Money out \$100\.00\.$/)).toBeTruthy();
    expect(screen.getAllByLabelText(/^Paycheck, .*, No category\. Money in \$2,600\.00\.$/).length).toBeGreaterThan(0);
    expect(screen.queryAllByLabelText(/\. Spent \$[\d,.]+\.$/)).toHaveLength(0);
    expect(screen.queryByText(/· Income$/)).toBeNull();
  });

  it('expands a group to show its categories when tapped', async () => {
    await render(<HomeScreen />, { wrapper: Wrapper });
    await screen.findByText(SAMPLE_BANNER_TEXT);

    expect(screen.queryByText('Over by $42.00')).toBeNull();
    const wants = screen.getByRole('button', { name: /^Wants\./ });
    expect(wants.props.accessibilityState).toEqual(expect.objectContaining({ expanded: false }));

    await fireEvent.press(wants);

    expect(screen.getByText('Over by $42.00')).toBeTruthy();
    expect(screen.getByText('Spent $342.00 of $300.00 (114%)')).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /^Wants\./ }).props.accessibilityState,
    ).toEqual(expect.objectContaining({ expanded: true }));
  });

  it('shows a saved snapshot and when it was synced', async () => {
    const real = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    real.server_id = 'abc';
    real.transactions[0].description = 'Lakeside Bakery';
    const syncedAt = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000 - 60_000).toISOString();
    await AsyncStorage.setItem(
      SNAPSHOT_STORAGE_KEY,
      JSON.stringify({ snapshot: real, last_synced_at: syncedAt }),
    );

    await render(<HomeScreen />, { wrapper: Wrapper });

    expect(await screen.findByText('Lakeside Bakery')).toBeTruthy();
    expect(screen.getByText('Last synced: 2 days ago')).toBeTruthy();
    expect(screen.queryByText(SAMPLE_BANNER_TEXT)).toBeNull();
  });

  it('shows a friendly message (not a crash) when the saved snapshot is broken', async () => {
    await AsyncStorage.setItem(
      SNAPSHOT_STORAGE_KEY,
      JSON.stringify({ snapshot: { contract: 1, budget: 'oops' }, last_synced_at: new Date().toISOString() }),
    );

    await render(<HomeScreen />, { wrapper: Wrapper });

    expect(await screen.findByText(SNAPSHOT_INVALID_MESSAGE)).toBeTruthy();
    expect(screen.getByText(SAMPLE_BANNER_TEXT)).toBeTruthy();
  });

  it('copes with storage that is not even JSON', async () => {
    await AsyncStorage.setItem(SNAPSHOT_STORAGE_KEY, '{not json');
    await render(<HomeScreen />, { wrapper: Wrapper });
    expect(await screen.findByText(SNAPSHOT_INVALID_MESSAGE)).toBeTruthy();
  });
});

describe('Taxes screen', () => {
  it('summarises the tax section with an estimates note', async () => {
    await render(<TaxesScreen />, { wrapper: Wrapper });

    expect(await screen.findByText(SAMPLE_BANNER_TEXT)).toBeTruthy();
    expect(screen.getByText(/Estimates, not tax advice/)).toBeTruthy();
    expect(screen.getByText('$450.00')).toBeTruthy(); // donations
    expect(screen.getByText('-$120.00')).toBeTruthy(); // short-term loss
    expect(screen.getByText('$840.00')).toBeTruthy(); // long-term gain
    expect(screen.getByText('Medical')).toBeTruthy();
    expect(screen.getByText('Home office')).toBeTruthy();
    expect(screen.getAllByText('estimate').length).toBe(3);
  });
});
