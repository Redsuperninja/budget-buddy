import { BodyText, Card, Screen } from '@/components/Screen';

export default function HomeScreen() {
  return (
    <Screen title="Your budget" intro="This is where you'll see how your money is doing this month.">
      <Card>
        <BodyText>Nothing to show yet.</BodyText>
        <BodyText muted>
          Once your phone is connected to Budget Buddy on your computer, your spending by category
          will show up here.
        </BodyText>
      </Card>
    </Screen>
  );
}
