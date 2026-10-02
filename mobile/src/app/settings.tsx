import { BigButton, BodyText, Card, Screen } from '@/components/Screen';

export default function SettingsScreen() {
  return (
    <Screen title="Settings">
      <Card>
        <BodyText>Not connected to your computer yet</BodyText>
        <BodyText muted>
          Connecting lets your phone get your latest budget from Budget Buddy on your computer.
        </BodyText>
      </Card>
      <BigButton label="Connect" disabled accessibilityHint="Connecting is coming soon" />
      <BodyText muted>Coming soon: connecting your phone isn't ready yet.</BodyText>
    </Screen>
  );
}
