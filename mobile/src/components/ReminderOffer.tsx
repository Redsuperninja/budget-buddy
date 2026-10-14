import { useState } from 'react';
import { Text } from 'react-native';

import { BigButton, BodyText, Card } from '@/components/Screen';
import { answerReminderOffer } from '@/sync/reminders';
import { useSnapshot } from '@/sync/store';
import { useTheme } from '@/theme';

export const REMINDER_OFFER_TEXT =
  'Budget Buddy can remind you to sync every few days, so the budget on your phone stays up to date.';

/** Shown once, right after the first successful sync (contract §9): one line, then Allow or Not now. */
export function ReminderOffer({ onDone }: { onDone: () => void }) {
  const t = useTheme();
  const { snapshot, isSample, lastSyncedAt } = useSnapshot();
  const [message, setMessage] = useState<string | null>(null);
  const ctx = { lastSyncedAt, suggestedDays: isSample ? null : snapshot.settings.reminder_days_default };

  const answer = async (allow: boolean) => {
    const problem = await answerReminderOffer(allow, ctx);
    if (problem) setMessage(problem);
    else onDone();
  };

  return (
    <Card>
      <BodyText>{REMINDER_OFFER_TEXT}</BodyText>
      {message ? (
        <Text accessibilityRole="alert" style={{ fontSize: t.fontSizes.body, color: t.colors.negative }}>
          {message}
        </Text>
      ) : (
        <>
          <BigButton label="Allow reminders" onPress={() => void answer(true)} />
          <BigButton label="Not now" onPress={() => void answer(false)} />
        </>
      )}
    </Card>
  );
}
