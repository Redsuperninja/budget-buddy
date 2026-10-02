import { BigButton, BodyText, Screen } from '@/components/Screen';

export default function AddReceiptScreen() {
  return (
    <Screen
      title="Add a receipt"
      intro="Snap a photo of a receipt and Budget Buddy will keep it safe until you're home.">
      <BigButton
        label="Take photo"
        disabled
        accessibilityHint="Taking photos is coming soon"
      />
      <BodyText muted>Coming soon: taking receipt photos isn't ready yet.</BodyText>
    </Screen>
  );
}
