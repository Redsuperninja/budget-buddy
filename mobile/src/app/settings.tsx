import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';

import { BigButton, BodyText, Card, Screen } from '@/components/Screen';
import { LastSynced } from '@/components/SnapshotNotices';
import { SyncPanel } from '@/components/SyncPanel';
import { SyncReminders } from '@/components/SyncReminders';
import { loadCredentials } from '@/sync/credentials';

export default function SettingsScreen() {
  const router = useRouter();
  const [computer, setComputer] = useState<string | null>(null);

  // Re-check each time the tab is shown, so it updates right after pairing.
  useFocusEffect(
    useCallback(() => {
      let active = true;
      void loadCredentials().then((c) => {
        if (active) setComputer(c ? c.server_name : null);
      });
      return () => {
        active = false;
      };
    }, []),
  );

  return (
    <Screen title="Settings">
      <Card>
        <BodyText>{computer ? `Connected to ${computer}` : 'Not connected to your computer yet'}</BodyText>
        <BodyText muted>
          Connecting lets your phone get your latest budget from Budget Buddy on your computer.
        </BodyText>
      </Card>
      <LastSynced />
      <SyncPanel />
      <SyncReminders />
      <BigButton
        label={computer ? 'Connect to a different computer' : 'Connect to your computer'}
        onPress={() => router.push('/pair')}
        accessibilityHint="Opens the screen where you scan the code from your computer"
      />
    </Screen>
  );
}
