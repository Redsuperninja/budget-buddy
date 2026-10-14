import { useRouter } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Text } from 'react-native';

import { ReminderOffer } from '@/components/ReminderOffer';
import { BigButton, Card } from '@/components/Screen';
import { getNeedsAttention } from '@/sync/credentials';
import { shouldOfferReminders } from '@/sync/reminders';
import { runSync } from '@/sync/runSync';
import { useSnapshot } from '@/sync/store';
import { useTheme } from '@/theme';

export const SYNCING_TEXT = 'Syncing...';
export const SYNCED_TEXT = 'Synced just now';

type Status = { name: 'idle' } | { name: 'syncing' } | { name: 'done' } | { name: 'error'; message: string };

function PairAgainButton() {
  const router = useRouter(); // only mounted when needed, so screens without a router still render
  return (
    <BigButton
      label="Pair again"
      onPress={() => router.push('/pair')}
      accessibilityHint="Opens the screen where you scan the code from your computer"
    />
  );
}

/** The "Sync now" button with its status line (syncing, synced, or a plain-English problem). */
export function SyncPanel() {
  const t = useTheme();
  const { saveSnapshot } = useSnapshot();
  const [status, setStatus] = useState<Status>({ name: 'idle' });
  const [needsAttention, setNeedsAttention] = useState(false);
  const [offerReminders, setOfferReminders] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    void getNeedsAttention().then((on) => {
      if (mounted.current) setNeedsAttention(on);
    });
    return () => {
      mounted.current = false;
    };
  }, []);

  const onSync = async () => {
    setStatus({ name: 'syncing' });
    const outcome = await runSync(async (snapshot) => saveSnapshot(snapshot));
    if (!mounted.current) return;
    if (outcome.ok) {
      setNeedsAttention(false);
      setStatus({ name: 'done' });
      const offer = await shouldOfferReminders();
      if (mounted.current) setOfferReminders(offer);
    } else {
      setNeedsAttention(outcome.needsAttention);
      setStatus({ name: 'error', message: outcome.message });
    }
  };

  const syncing = status.name === 'syncing';
  return (
    <>
      <BigButton
        label={syncing ? SYNCING_TEXT : 'Sync now'}
        disabled={syncing}
        onPress={() => void onSync()}
        accessibilityHint="Gets your latest budget from your computer. Your phone must be on home Wi-Fi."
      />
      {status.name === 'done' ? (
        <Text accessibilityRole="alert" style={{ fontSize: t.fontSizes.body, color: t.colors.positive }}>
          {SYNCED_TEXT}
        </Text>
      ) : null}
      {status.name === 'error' ? (
        <Card>
          <Text accessibilityRole="alert" style={{ fontSize: t.fontSizes.body, lineHeight: 26, color: t.colors.negative }}>
            {status.message}
          </Text>
        </Card>
      ) : null}
      {offerReminders ? <ReminderOffer onDone={() => setOfferReminders(false)} /> : null}
      {needsAttention ? <PairAgainButton /> : null}
    </>
  );
}
