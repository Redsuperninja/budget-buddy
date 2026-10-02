import type { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '@/theme';

type ScreenProps = {
  title: string;
  intro?: string;
  children?: ReactNode;
};

/** Standard screen wrapper: safe area, scrolling, big title, optional intro line. */
export function Screen({ title, intro, children }: ScreenProps) {
  const t = useTheme();
  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: t.colors.background }}>
      <ScrollView contentContainerStyle={{ padding: t.spacing.lg, gap: t.spacing.lg }}>
        <Text
          accessibilityRole="header"
          style={{ fontSize: t.fontSizes.title, fontWeight: '700', color: t.colors.text }}>
          {title}
        </Text>
        {intro ? (
          <Text style={{ fontSize: t.fontSizes.body, lineHeight: 26, color: t.colors.textMuted }}>
            {intro}
          </Text>
        ) : null}
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

/** A soft rounded box for grouping content. */
export function Card({ children }: { children: ReactNode }) {
  const t = useTheme();
  return (
    <View
      style={{
        backgroundColor: t.colors.surface,
        borderColor: t.colors.border,
        borderWidth: StyleSheet.hairlineWidth,
        borderRadius: t.radius.md,
        padding: t.spacing.lg,
        gap: t.spacing.sm,
      }}>
      {children}
    </View>
  );
}

/** Body text in the theme's colors. */
export function BodyText({ children, muted }: { children: ReactNode; muted?: boolean }) {
  const t = useTheme();
  return (
    <Text
      style={{
        fontSize: t.fontSizes.body,
        lineHeight: 26,
        color: muted ? t.colors.textMuted : t.colors.text,
      }}>
      {children}
    </Text>
  );
}

type BigButtonProps = {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  accessibilityHint?: string;
};

/** A large, full-width button that is easy to tap. */
export function BigButton({ label, onPress, disabled, accessibilityHint }: BigButtonProps) {
  const t = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled }}
      accessibilityHint={accessibilityHint}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({
        minHeight: t.minTouchSize + 8,
        borderRadius: t.radius.md,
        paddingHorizontal: t.spacing.lg,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: disabled ? t.colors.disabled : t.colors.primary,
        opacity: pressed ? 0.85 : 1,
      })}>
      <Text
        style={{
          fontSize: t.fontSizes.large,
          fontWeight: '700',
          color: disabled ? t.colors.onDisabled : t.colors.onPrimary,
        }}>
        {label}
      </Text>
    </Pressable>
  );
}
