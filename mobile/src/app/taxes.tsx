import { StyleSheet, Text, View } from 'react-native';

import { BodyText, Card, Screen } from '@/components/Screen';
import { LastSynced, SnapshotNotices } from '@/components/SnapshotNotices';
import { formatCents } from '@/lib/money';
import { useSnapshot } from '@/sync/store';
import { useTheme } from '@/theme';

const TAX_NOTE = 'Estimates, not tax advice. Check with a tax professional before you file.';

function EstimateTag() {
  const t = useTheme();
  return (
    <Text
      style={{
        alignSelf: 'flex-start',
        fontSize: t.fontSizes.small - 1,
        fontWeight: '700',
        color: t.colors.warning,
        borderColor: t.colors.warning,
        borderWidth: 1,
        borderRadius: t.radius.sm,
        paddingHorizontal: t.spacing.sm,
        paddingVertical: 2,
      }}>
      estimate
    </Text>
  );
}

function Row({ label, value, estimate, note }: { label: string; value: string; estimate?: boolean; note?: string }) {
  const t = useTheme();
  const a11y = [label, value, note, estimate ? 'This is an estimate.' : undefined].filter(Boolean).join('. ');
  return (
    <View
      accessible
      accessibilityLabel={a11y}
      style={{
        minHeight: t.minTouchSize,
        paddingVertical: t.spacing.sm,
        flexDirection: 'row',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: t.spacing.sm,
        borderBottomColor: t.colors.border,
        borderBottomWidth: StyleSheet.hairlineWidth,
      }}>
      <View style={{ flexShrink: 1, gap: 2 }}>
        <Text style={{ fontSize: t.fontSizes.body, color: t.colors.text }}>{label}</Text>
        {note ? <Text style={{ fontSize: t.fontSizes.small, color: t.colors.textMuted }}>{note}</Text> : null}
        {estimate ? <EstimateTag /> : null}
      </View>
      <Text style={{ fontSize: t.fontSizes.body, fontWeight: '700', color: t.colors.text }}>{value}</Text>
    </View>
  );
}

function SectionTitle({ children }: { children: string }) {
  const t = useTheme();
  return (
    <Text accessibilityRole="header" style={{ fontSize: t.fontSizes.large, fontWeight: '700', color: t.colors.text }}>
      {children}
    </Text>
  );
}

/** "-$120.00" reads as "a loss of $120.00" for clarity. */
function gainNote(cents: number): string | undefined {
  if (cents < 0) return 'A loss';
  if (cents > 0) return 'A gain';
  return undefined;
}

export default function TaxesScreen() {
  const t = useTheme();
  const { snapshot } = useSnapshot();
  const { tax, currency } = snapshot;
  const fmt = (c: number) => formatCents(c, currency);
  const gains = tax.realized_gains;

  return (
    <Screen title="Taxes" intro={`A simple summary for the ${tax.year} tax year.`}>
      <SnapshotNotices />
      <LastSynced />

      <Card>
        <Text
          accessibilityRole="text"
          style={{ fontSize: t.fontSizes.body, fontWeight: '700', color: t.colors.text }}>
          {TAX_NOTE}
        </Text>
        {tax.disclaimer ? <BodyText muted>{tax.disclaimer}</BodyText> : null}
      </Card>

      <View>
        <SectionTitle>Donations</SectionTitle>
        <Row label="Given to charity this year" value={fmt(tax.donations_total_cents)} />
      </View>

      <View>
        <SectionTitle>Stock sales</SectionTitle>
        <Row
          label="Short-term (held 1 year or less)"
          value={fmt(gains.short_term_cents)}
          note={gainNote(gains.short_term_cents)}
          estimate={gains.is_estimate}
        />
        <Row
          label="Long-term (held more than 1 year)"
          value={fmt(gains.long_term_cents)}
          note={gainNote(gains.long_term_cents)}
          estimate={gains.is_estimate}
        />
      </View>

      <View>
        <SectionTitle>Deductions</SectionTitle>
        {tax.deductions.length === 0 ? (
          <BodyText muted>No deductions recorded yet.</BodyText>
        ) : (
          tax.deductions.map((d, i) => (
            <Row
              key={`${d.kind}-${i}`}
              label={d.label || d.kind}
              value={fmt(d.amount_cents)}
              estimate={d.is_estimate}
            />
          ))
        )}
      </View>
    </Screen>
  );
}
