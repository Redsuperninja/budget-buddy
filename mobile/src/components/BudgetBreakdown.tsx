import Ionicons from '@expo/vector-icons/Ionicons';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { barPercent, lineStatus, percentUsed, statusText } from '@/lib/budget';
import type { LineStatus } from '@/lib/budget';
import { formatCents } from '@/lib/money';
import type { BudgetGroup, GroupKey } from '@/sync/snapshot';
import { useTheme } from '@/theme';
import type { Theme } from '@/theme';

function statusColor(t: Theme, status: LineStatus): string {
  switch (status) {
    case 'over':
      return t.colors.negative;
    case 'close':
      return t.colors.warning;
    case 'goal_met':
    case 'on_track':
      return t.colors.positive;
    case 'in_progress':
      return t.colors.primary;
    case 'no_target':
      return t.colors.textMuted;
  }
}

/** Simple horizontal bar built from Views. Hidden from screen readers (the text says it all). */
export function ProgressBar({ percent, color, thin }: { percent: number; color: string; thin?: boolean }) {
  const t = useTheme();
  const height = thin ? 10 : 16;
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{
        height,
        borderRadius: height / 2,
        backgroundColor: t.colors.background,
        borderColor: t.colors.border,
        borderWidth: StyleSheet.hairlineWidth,
        overflow: 'hidden',
      }}>
      <View style={{ width: `${percent}%`, height: '100%', backgroundColor: color }} />
    </View>
  );
}

type LineProps = {
  group: GroupKey;
  name: string;
  actualCents: number;
  targetCents: number;
  currency: string;
};

/** "Spent $1,580.00 of $2,600.00 (60%)" or "Saved ..." */
function amountsText({ group, actualCents, targetCents, currency }: LineProps): string {
  const verb = group === 'savings' ? 'Saved' : 'Spent';
  const actual = formatCents(actualCents, currency);
  if (targetCents <= 0) return `${verb} ${actual}`;
  const pct = percentUsed(actualCents, targetCents);
  return `${verb} ${actual} of ${formatCents(targetCents, currency)} (${pct}%)`;
}

function CategoryLine(props: LineProps) {
  const t = useTheme();
  const { group, name, actualCents, targetCents, currency } = props;
  const status = lineStatus(group, actualCents, targetCents);
  const amounts = amountsText(props);
  const statusWords = statusText(group, actualCents, targetCents, currency);
  return (
    <View
      accessible
      accessibilityLabel={`${name}. ${amounts}. ${statusWords}.`}
      style={{ gap: t.spacing.xs, paddingVertical: t.spacing.sm }}>
      <Text style={{ fontSize: t.fontSizes.body, fontWeight: '600', color: t.colors.text }}>{name}</Text>
      <ProgressBar thin percent={barPercent(actualCents, targetCents)} color={statusColor(t, status)} />
      <Text style={{ fontSize: t.fontSizes.small, color: t.colors.textMuted }}>{amounts}</Text>
      <Text style={{ fontSize: t.fontSizes.small, fontWeight: '600', color: statusColor(t, status) }}>
        {statusWords}
      </Text>
    </View>
  );
}

/** One budget group (Needs / Wants / Savings). Tap to show its categories. */
export function GroupCard({ group, currency }: { group: BudgetGroup; currency: string }) {
  const t = useTheme();
  const [expanded, setExpanded] = useState(false);
  const line: LineProps = {
    group: group.group,
    name: group.name,
    actualCents: group.actual_cents,
    targetCents: group.target_cents,
    currency,
  };
  const status = lineStatus(group.group, group.actual_cents, group.target_cents);
  const color = statusColor(t, status);
  const amounts = amountsText(line);
  const statusWords = statusText(group.group, group.actual_cents, group.target_cents, currency);

  return (
    <View
      style={{
        backgroundColor: t.colors.surface,
        borderColor: t.colors.border,
        borderWidth: StyleSheet.hairlineWidth,
        borderRadius: t.radius.md,
        overflow: 'hidden',
      }}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        accessibilityLabel={`${group.name}. ${amounts}. ${statusWords}.`}
        accessibilityHint={expanded ? 'Hides the categories' : 'Shows the categories'}
        onPress={() => setExpanded((e) => !e)}
        style={({ pressed }) => ({
          minHeight: t.minTouchSize,
          padding: t.spacing.lg,
          gap: t.spacing.sm,
          opacity: pressed ? 0.85 : 1,
        })}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: t.spacing.sm }}>
          <Text
            style={{ flex: 1, fontSize: t.fontSizes.large, fontWeight: '700', color: t.colors.text }}>
            {group.name}
          </Text>
          <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={26} color={t.colors.textMuted} />
        </View>
        <ProgressBar percent={barPercent(group.actual_cents, group.target_cents)} color={color} />
        <Text style={{ fontSize: t.fontSizes.body, color: t.colors.text }}>{amounts}</Text>
        <Text style={{ fontSize: t.fontSizes.body, fontWeight: '700', color }}>{statusWords}</Text>
      </Pressable>
      {expanded ? (
        <View
          style={{
            paddingHorizontal: t.spacing.lg,
            paddingBottom: t.spacing.md,
            borderTopColor: t.colors.border,
            borderTopWidth: StyleSheet.hairlineWidth,
          }}>
          {group.categories.length === 0 ? (
            <Text style={{ fontSize: t.fontSizes.body, color: t.colors.textMuted, paddingVertical: t.spacing.sm }}>
              No categories yet.
            </Text>
          ) : (
            group.categories.map((c) => (
              <CategoryLine
                key={c.id}
                group={group.group}
                name={c.name}
                actualCents={c.actual_cents}
                targetCents={c.target_cents}
                currency={currency}
              />
            ))
          )}
        </View>
      ) : null}
    </View>
  );
}
