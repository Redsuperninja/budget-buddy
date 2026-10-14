import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactNode } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import HomeScreen from '@/app/index';
import TaxesScreen, { DEDUCTIONS_NOTE, DEDUCTIONS_TITLE, GAINS_MAY_CHANGE_TAG, MISSING_INFO_TAG } from '@/app/taxes';
import { SAMPLE_BANNER_TEXT } from '@/components/SnapshotNotices';
import { oldMonthNotice, phoneMonth } from '@/lib/months';
import { SAMPLE_SNAPSHOT } from '@/sync/sampleSnapshot';
import { SNAPSHOT_INVALID_MESSAGE } from '@/sync/snapshot';
import { LEGACY_SNAPSHOT_KEY, SNAPSHOT_STORAGE_KEY, SnapshotProvider } from '@/sync/store';

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
    expect(screen.getByText(/2 transactions need a category on your computer\. They are not counted/)).toBeTruthy();
    expect(screen.getByText('$50.00 owed')).toBeTruthy();
    expect(screen.getByText('Take-home pay so far')).toBeTruthy();
    expect(screen.queryByText('Income so far')).toBeNull();
    expect(screen.getByText('of take-home pay ($600.00 saved)')).toBeTruthy();
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

  // A saved summary for `month`, with its period made consistent (parsePeriod checks it).
  async function saveSummaryFor(month: string) {
    const copy = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    const [y, m] = month.split('-').map(Number);
    const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
    copy.period = { month, start: `${month}-01`, end: `${month}-${days}`, days_elapsed: days, days_in_month: days };
    await AsyncStorage.setItem(
      LEGACY_SNAPSHOT_KEY, // a plain copy from before encryption, sealed on first read
      JSON.stringify({ snapshot: copy, last_synced_at: new Date().toISOString() }),
    );
  }

  it('says when the saved summary is from an earlier month', async () => {
    const now = new Date();
    const earlier = phoneMonth(new Date(now.getFullYear(), now.getMonth() - 1, 15));
    await saveSummaryFor(earlier);

    await render(<HomeScreen />, { wrapper: Wrapper });

    expect(await screen.findByText(oldMonthNotice(earlier, now) as string)).toBeTruthy();
  });

  it("doesn't flag a summary from this month", async () => {
    await saveSummaryFor(phoneMonth());

    await render(<HomeScreen />, { wrapper: Wrapper });

    expect(await screen.findByText('Left to spend')).toBeTruthy();
    expect(screen.queryByText(/summary\. Sync on your home Wi-Fi to see/)).toBeNull();
  });

  it('shows a saved snapshot and when it was synced', async () => {
    const real = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    real.server_id = 'abc';
    real.transactions[0].description = 'Lakeside Bakery';
    const syncedAt = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000 - 60_000).toISOString();
    await AsyncStorage.setItem(
      LEGACY_SNAPSHOT_KEY, // a plain copy from before encryption, sealed on first read
      JSON.stringify({ snapshot: real, last_synced_at: syncedAt }),
    );

    await render(<HomeScreen />, { wrapper: Wrapper });

    expect(await screen.findByText('Lakeside Bakery')).toBeTruthy();
    expect(screen.getByText('Last synced: 2 days ago')).toBeTruthy();
    expect(screen.queryByText(SAMPLE_BANNER_TEXT)).toBeNull();
  });

  it('shows a friendly message (not a crash) when the saved snapshot is broken', async () => {
    await AsyncStorage.setItem(
      LEGACY_SNAPSHOT_KEY, // a plain copy from before encryption, sealed on first read
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
    expect(screen.getAllByText(MISSING_INFO_TAG).length).toBe(1);
    expect(screen.getAllByText(GAINS_MAY_CHANGE_TAG).length).toBe(2);
    expect(screen.queryByText('estimate')).toBeNull();
  });

  it('does not call recorded expenses "Deductions" and explains why', async () => {
    await render(<TaxesScreen />, { wrapper: Wrapper });
    await screen.findByText(SAMPLE_BANNER_TEXT);

    expect(DEDUCTIONS_TITLE).toBe('Possibly deductible expenses');
    expect(screen.getByRole('header', { name: 'Possibly deductible expenses' })).toBeTruthy();
    expect(screen.queryByText('Deductions')).toBeNull();
    expect(screen.getByText(DEDUCTIONS_NOTE)).toBeTruthy();
    expect(DEDUCTIONS_NOTE).toMatch(/itemizing and income limits/);
  });

  it('uses the agreed tax wording', async () => {
    await render(<TaxesScreen />, { wrapper: Wrapper });
    await screen.findByText(SAMPLE_BANNER_TEXT);

    expect(screen.getByText("Donations you've recorded this year")).toBeTruthy();
    expect(screen.queryByText('Given to charity this year')).toBeNull();
    expect(
      screen.getAllByLabelText(/May change: possible wash sale\.$/).length,
    ).toBe(2);
  });
});
