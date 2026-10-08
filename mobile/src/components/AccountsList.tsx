import { StyleSheet, Text, View } from 'react-native';

import { accountKindLabel, formatAccountBalance, isDebtKind } from '@/lib/accounts';
import { formatDay } from '@/lib/dates';
import type { SnapshotAccount } from '@/sync/snapshot';
import { useTheme } from '@/theme';

function AccountRow({ account, currency }: { account: SnapshotAccount; currency: string }) {
  const t = useTheme();
  const balance = formatAccountBalance(account, currency);
  const owed = isDebtKind(account.kind) && account.balance_cents < 0;
  const kind = accountKindLabel(account.kind);
  return (
    <View
      accessible
      accessibilityLabel={`${account.name}, ${kind}. ${balance}. As of ${formatDay(account.balance_as_of, 'long')}.`}
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
        <Text style={{ fontSize: t.fontSizes.body, color: t.colors.text }}>{account.name}</Text>
        <Text style={{ fontSize: t.fontSizes.small, color: t.colors.textMuted }}>
          {kind} · as of {formatDay(account.balance_as_of)}
        </Text>
      </View>
      <Text style={{ fontSize: t.fontSizes.body, fontWeight: '600', color: owed ? t.colors.negative : t.colors.text }}>
        {balance}
      </Text>
    </View>
  );
}

/** Account balances, with card and loan debt shown as "owed". Renders nothing when there are no accounts. */
export function AccountsList({ accounts, currency }: { accounts: SnapshotAccount[]; currency: string }) {
  const t = useTheme();
  if (accounts.length === 0) return null;
  return (
    <View style={{ gap: t.spacing.sm }}>
      <Text accessibilityRole="header" style={{ fontSize: t.fontSizes.large, fontWeight: '700', color: t.colors.text }}>
        Your accounts
      </Text>
      <View>
        {accounts.map((a) => (
          <AccountRow key={a.id} account={a} currency={currency} />
        ))}
      </View>
    </View>
  );
}
