import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import type { TextInputProps } from 'react-native';

import { useTheme } from '@/theme';

/** A labelled text box, big enough to tap (shared by forms). */
export function TextField({ label, ...input }: { label: string } & TextInputProps) {
  const t = useTheme();
  return (
    <View style={{ gap: t.spacing.xs }}>
      <Text style={{ fontSize: t.fontSizes.body, color: t.colors.text }}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={t.colors.textMuted}
        {...input}
        style={[
          {
            minHeight: t.minTouchSize,
            borderRadius: t.radius.md,
            borderWidth: StyleSheet.hairlineWidth,
            borderColor: t.colors.border,
            backgroundColor: t.colors.surface,
            color: t.colors.text,
            fontSize: t.fontSizes.body,
            padding: t.spacing.md,
          },
          input.style,
        ]}
      />
    </View>
  );
}

/** One choice among several, shown as a row of tappable chips (a radio group for screen readers). */
export function ChoiceChips<T extends string | number>({
  choices,
  selected,
  onChoose,
  disabled,
}: {
  choices: readonly { value: T; label: string }[];
  selected: T | null;
  onChoose: (value: T) => void;
  disabled?: boolean;
}) {
  const t = useTheme();
  return (
    <View accessibilityRole="radiogroup" style={{ flexDirection: 'row', flexWrap: 'wrap', gap: t.spacing.sm }}>
      {choices.map(({ value, label }) => {
        const on = selected === value;
        return (
          <Pressable
            key={String(value)}
            accessibilityRole="radio"
            accessibilityLabel={label}
            accessibilityState={{ checked: on, disabled: Boolean(disabled) }}
            disabled={disabled}
            onPress={() => onChoose(value)}
            style={{
              minHeight: t.minTouchSize,
              justifyContent: 'center',
              paddingHorizontal: t.spacing.md,
              borderRadius: t.radius.md,
              borderWidth: 2,
              borderColor: on ? t.colors.primary : t.colors.border,
              backgroundColor: on ? t.colors.primary : t.colors.surface,
            }}>
            <Text style={{ fontSize: t.fontSizes.body, color: on ? t.colors.onPrimary : t.colors.text }}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}
