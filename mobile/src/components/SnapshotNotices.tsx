import Ionicons from '@expo/vector-icons/Ionicons';
import { Text, View } from 'react-native';

import { formatLastSynced } from '@/lib/dates';
import { useSnapshot } from '@/sync/store';
import { useTheme } from '@/theme';

export const SAMPLE_BANNER_TEXT =
  'Showing sample data. Connect to your computer in Settings to see your real budget.';

function Notice({ icon, text, tone }: { icon: 'information-circle' | 'alert-circle'; text: string; tone: 'info' | 'problem' }) {
  const t = useTheme();
  const accent = tone === 'problem' ? t.colors.negative : t.colors.primary;
  return (
    <View
      accessible
      accessibilityRole={tone === 'problem' ? 'alert' : 'text'}
      accessibilityLabel={text}
      style={{
        flexDirection: 'row',
        gap: t.spacing.sm,
        alignItems: 'flex-start',
        padding: t.spacing.md,
        borderRadius: t.radius.md,
        borderWidth: 2,
        borderColor: accent,
        backgroundColor: t.colors.surface,
      }}>
      <Ionicons name={icon} size={26} color={accent} />
      <Text style={{ flex: 1, fontSize: t.fontSizes.body, color: t.colors.text }}>{text}</Text>
    </View>
  );
}

/** Banners for sample data and an unreadable saved snapshot. Renders nothing when all is well. */
export function SnapshotNotices() {
  const { isSample, loadError } = useSnapshot();
  return (
    <>
      {loadError ? <Notice icon="alert-circle" tone="problem" text={loadError} /> : null}
      {isSample ? <Notice icon="information-circle" tone="info" text={SAMPLE_BANNER_TEXT} /> : null}
    </>
  );
}

/** "Last synced: 2 days ago" / "Never synced". */
export function LastSynced() {
  const t = useTheme();
  const { lastSyncedAt } = useSnapshot();
  const words = formatLastSynced(lastSyncedAt);
  const text = lastSyncedAt === null ? words : `Last synced: ${words}`;
  return <Text style={{ fontSize: t.fontSizes.small, color: t.colors.textMuted }}>{text}</Text>;
}
