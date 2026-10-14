import { useEffect, useRef, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { BodyText, Card } from '@/components/Screen';
import { useSnapshot } from '@/sync/store';
import {
  chooseReminderDays,
  effectiveDays,
  loadReminderChoice,
  REMINDER_CHOICES,
  reminderLabel,
} from '@/sync/reminders';
import type { ReminderChoice } from '@/sync/reminders';
import { useTheme } from '@/theme';

export const REMINDERS_TITLE = 'Remind me to sync';

/**
 * Settings: remind every 1, 2 or 3 days after your last sync, or Off (roadmap #21, contract §9). Until you
 * pick, your computer's suggestion is used and marked. Picking a number asks to show notifications.
 */
export function SyncReminders() {
  const t = useTheme();
  const { snapshot, isSample, lastSyncedAt } = useSnapshot();
  const [choice, setChoice] = useState<ReminderChoice | null | undefined>(undefined); // undefined: loading
  const [message, setMessage] = useState<string | null>(null);
  const mounted = useRef(true);
  const suggested = isSample ? null : snapshot.settings.reminder_days_default;
  const shown = choice === undefined ? null : effectiveDays(choice, suggested);

  useEffect(() => {
    mounted.current = true;
    void loadReminderChoice().then((c) => {
      if (mounted.current) setChoice(c);
    });
    return () => {
      mounted.current = false;
    };
  }, []);

  const choose = async (next: ReminderChoice) => {
    const problem = await chooseReminderDays(next, { lastSyncedAt, suggestedDays: suggested });
    if (!mounted.current) return;
    setMessage(problem);
    setChoice(await loadReminderChoice()); // what's really saved
  };

  return (
    <Card>
      <Text accessibilityRole="header" style={{ fontSize: t.fontSizes.body, fontWeight: '700', color: t.colors.text }}>
        {REMINDERS_TITLE}
      </Text>
      <BodyText muted>
        A reminder on this phone when it hasn't synced for a while, so your budget here stays up to date. Never at
        night (9 PM to 9 AM).
      </BodyText>
      <View accessibilityRole="radiogroup" style={{ flexDirection: 'row', flexWrap: 'wrap', gap: t.spacing.sm }}>
        {REMINDER_CHOICES.map((option) => {
          const selected = shown === option;
          const label = reminderLabel(option) + (option === suggested ? ' (suggested)' : '');
          return (
            <Pressable
              key={option}
              accessibilityRole="radio"
              accessibilityLabel={label}
              accessibilityState={{ checked: selected, disabled: choice === undefined }}
              disabled={choice === undefined}
              onPress={() => void choose(option)}
              style={{
                minHeight: t.minTouchSize,
                justifyContent: 'center',
                paddingHorizontal: t.spacing.md,
                borderRadius: t.radius.md,
                borderWidth: 2,
                borderColor: selected ? t.colors.primary : t.colors.border,
                backgroundColor: selected ? t.colors.primary : t.colors.surface,
              }}>
              <Text style={{ fontSize: t.fontSizes.body, color: selected ? t.colors.onPrimary : t.colors.text }}>{label}</Text>
            </Pressable>
          );
        })}
      </View>
      {message ? (
        <Text accessibilityRole="alert" style={{ fontSize: t.fontSizes.body, color: t.colors.negative }}>
          {message}
        </Text>
      ) : null}
    </Card>
  );
}
