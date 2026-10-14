import { StyleSheet, Text, View } from 'react-native';

import { BigButton, Card } from '@/components/Screen';
import { formatDay } from '@/lib/dates';
import { formatCents } from '@/lib/money';
import type { QueuedReceipt } from '@/receipts/receiptQueue';
import { useTheme } from '@/theme';

export const WAITING_TEXT = 'Waiting to sync';
export const UNREADABLE_TEXT =
  "Your waiting receipts can't be read on this phone any more (for example after restoring it). Clear them, then take the photos again.";

function ReceiptRow({
  receipt,
  currency,
  onDelete,
  onRetake,
}: {
  receipt: QueuedReceipt;
  currency: string;
  onDelete: () => void;
  onRetake: () => void;
}) {
  const t = useTheme();
  const name = receipt.merchant ?? 'Receipt';
  const total = receipt.total_cents === null ? '' : ` · ${formatCents(receipt.total_cents, currency)}`;
  const rejected = receipt.state === 'rejected';
  return (
    <View style={{ gap: t.spacing.xs, paddingVertical: t.spacing.sm, borderBottomColor: t.colors.border, borderBottomWidth: StyleSheet.hairlineWidth }}>
      <Text style={{ fontSize: t.fontSizes.body, color: t.colors.text }}>
        {name}
        {total} · {formatDay(receipt.captured_at.slice(0, 10))}
      </Text>
      <Text style={{ fontSize: t.fontSizes.small, color: rejected ? t.colors.negative : t.colors.textMuted }}>
        {rejected ? receipt.message : WAITING_TEXT}
      </Text>
      {rejected ? <BigButton label="Retake photo" onPress={onRetake} /> : null}
      <BigButton label={`Delete ${name}`} onPress={onDelete} />
    </View>
  );
}

/** Receipts on this phone that haven't gone to your computer yet, or a way out if they can't be read. */
export function WaitingReceipts({
  receipts,
  readable,
  currency,
  onDelete,
  onRetake,
  onClear,
}: {
  receipts: QueuedReceipt[];
  readable: boolean;
  currency: string;
  onDelete: (r: QueuedReceipt) => void;
  onRetake: (r: QueuedReceipt) => void;
  onClear: () => void;
}) {
  const t = useTheme();
  if (!readable) {
    return (
      <Card>
        <Text accessibilityRole="alert" style={{ fontSize: t.fontSizes.body, color: t.colors.negative }}>
          {UNREADABLE_TEXT}
        </Text>
        <BigButton label="Clear waiting receipts" onPress={onClear} />
      </Card>
    );
  }
  if (receipts.length === 0) return null;
  return (
    <Card>
      <Text accessibilityRole="header" style={{ fontSize: t.fontSizes.body, fontWeight: '700', color: t.colors.text }}>
        {receipts.length === 1 ? '1 receipt waiting' : `${receipts.length} receipts waiting`}
      </Text>
      {receipts.map((r) => (
        <ReceiptRow key={r.client_id} receipt={r} currency={currency} onDelete={() => onDelete(r)} onRetake={() => onRetake(r)} />
      ))}
    </Card>
  );
}
