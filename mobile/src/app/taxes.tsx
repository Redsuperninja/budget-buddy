import { BodyText, Card, Screen } from '@/components/Screen';

export default function TaxesScreen() {
  return (
    <Screen title="Taxes" intro="A simple summary to help at tax time.">
      <Card>
        <BodyText>Nothing to show yet.</BodyText>
        <BodyText muted>
          Your donations, stock sales, and other tax items will show up here after your phone is
          connected to your computer.
        </BodyText>
      </Card>
    </Screen>
  );
}
