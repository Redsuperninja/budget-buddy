import { StyleSheet, Text, View } from 'react-native';

import { GroupCard } from '@/components/BudgetBreakdown';
import { Card, Screen } from '@/components/Screen';
import { LastSynced, SnapshotNotices } from '@/components/SnapshotNotices';
import { categoriesById, monthHeadline, orderedGroups, recentTransactions, savingsStat, spentStat } from '@/lib/budget';
import { formatDay, formatMonth } from '@/lib/dates';
import { formatCents } from '@/lib/money';
import type { Snapshot, SnapshotTransaction } from '@/sync/snapshot';
import { useSnapshot } from '@/sync/store';
import { useTheme } from '@/theme';

function SectionTitle({ children }: { children: string }) {
  const t = useTheme();
  return (
    <Text accessibilityRole="header" style={{ fontSize: t.fontSizes.large, fontWeight: '700', color: t.colors.text }}>
      {children}
    </Text>
  );
}

function Stat({ label, value, note, color }: { label: string; value: string; note?: string; color?: string }) {
  const t = useTheme();
  return (
    <View accessible accessibilityLabel={[label, value, note].filter(Boolean).join('. ')} style={{ gap: 2 }}>
      <Text style={{ fontSize: t.fontSizes.small, color: t.colors.textMuted }}>{label}</Text>
      <Text style={{ fontSize: t.fontSizes.large, fontWeight: '700', color: color ?? t.colors.text }}>{value}</Text>
      {note ? <Text style={{ fontSize: t.fontSizes.small, color: t.colors.textMuted }}>{note}</Text> : null}
    </View>
  );
}

function Headline({ snapshot }: { snapshot: Snapshot }) {
  const t = useTheme();
  const h = monthHeadline(snapshot);
  const fmt = (c: number) => formatCents(c, snapshot.currency);
  const bigLabel = h.isOverBudget ? 'Over budget by' : 'Left to spend';
  const bigValue = fmt(Math.abs(h.leftToSpendCents));
  const bigColor = h.isOverBudget ? t.colors.negative : t.colors.text;
  return (
    <Card>
      <View accessible accessibilityLabel={`${bigLabel} ${bigValue} this month.`}>
        <Text style={{ fontSize: t.fontSizes.body, color: t.colors.textMuted }}>{bigLabel}</Text>
        <Text style={{ fontSize: t.fontSizes.money, fontWeight: '800', color: bigColor }}>{bigValue}</Text>
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', columnGap: t.spacing.xl, rowGap: t.spacing.md, marginTop: t.spacing.sm }}>
        <Stat
          label="Income so far"
          value={fmt(h.incomeReceivedCents)}
          note={`of ${fmt(h.incomeExpectedCents)} expected`}
        />
        <Stat label="Spent" {...spentStat(h, snapshot.currency)} />
        <Stat label="Savings rate" {...savingsStat(h, snapshot.currency)} />
      </View>
    </Card>
  );
}

function TransactionRow({
  tx,
  categoryName,
  currency,
}: {
  tx: SnapshotTransaction;
  categoryName: string;
  currency: string;
}) {
  const t = useTheme();
  const moneyIn = tx.amount_cents > 0;
  const amount = formatCents(Math.abs(tx.amount_cents), currency);
  const shown = moneyIn ? `+${amount}` : `-${amount}`;
  return (
    <View
      accessible
      accessibilityLabel={`${tx.description}, ${formatDay(tx.date, 'long')}, ${categoryName}. ${moneyIn ? 'Money in' : 'Spent'} ${amount}.`}
      style={{
        minHeight: t.minTouchSize,
        paddingVertical: t.spacing.sm,
        flexDirection: 'row',
        alignItems: 'center',
        gap: t.spacing.md,
        borderBottomColor: t.colors.border,
        borderBottomWidth: StyleSheet.hairlineWidth,
      }}>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: t.fontSizes.body, color: t.colors.text }}>{tx.description}</Text>
        <Text style={{ fontSize: t.fontSizes.small, color: t.colors.textMuted }}>
          {formatDay(tx.date)} · {categoryName}
        </Text>
      </View>
      <Text
        style={{
          fontSize: t.fontSizes.body,
          fontWeight: '600',
          color: moneyIn ? t.colors.positive : t.colors.text,
        }}>
        {shown}
      </Text>
    </View>
  );
}

function RecentActivity({ snapshot }: { snapshot: Snapshot }) {
  const t = useTheme();
  const recent = recentTransactions(snapshot, 10);
  const cats = categoriesById(snapshot);
  return (
    <View style={{ gap: t.spacing.sm }}>
      <SectionTitle>Recent activity</SectionTitle>
      {recent.length === 0 ? (
        <Text style={{ fontSize: t.fontSizes.body, color: t.colors.textMuted }}>No recent activity yet.</Text>
      ) : (
        <View>
          {recent.map((tx) => (
            <TransactionRow
              key={tx.id}
              tx={tx}
              currency={snapshot.currency}
              categoryName={
                tx.category_id === null
                  ? tx.amount_cents > 0
                    ? 'Income'
                    : 'No category'
                  : (cats.get(tx.category_id)?.name ?? 'Other')
              }
            />
          ))}
        </View>
      )}
    </View>
  );
}

export default function HomeScreen() {
  const t = useTheme();
  const { snapshot } = useSnapshot();
  return (
    <Screen title="Your budget" intro={formatMonth(snapshot.period.month)}>
      <SnapshotNotices />
      <LastSynced />
      <Headline snapshot={snapshot} />
      <View style={{ gap: t.spacing.md }}>
        <SectionTitle>Where your money is going</SectionTitle>
        <Text style={{ fontSize: t.fontSizes.small, color: t.colors.textMuted }}>
          Tap a group to see its categories.
        </Text>
        {orderedGroups(snapshot).map((g) => (
          <GroupCard key={g.group} group={g} currency={snapshot.currency} />
        ))}
      </View>
      <RecentActivity snapshot={snapshot} />
    </Screen>
  );
}
