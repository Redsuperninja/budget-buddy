/**
 * Budget Buddy theme: colors (light + dark), spacing, and font sizes.
 *
 * Text/background pairs are chosen to meet WCAG AA contrast (4.5:1 or better for body text).
 * Use `useTheme()` in components so the app follows the phone's light/dark setting.
 */
import { useColorScheme } from 'react-native';

export type ColorPalette = {
  background: string;
  surface: string;
  border: string;
  text: string;
  textMuted: string;
  primary: string;
  onPrimary: string;
  disabled: string;
  onDisabled: string;
  positive: string;
  negative: string;
  warning: string;
  tabInactive: string;
};

export const colors: { light: ColorPalette; dark: ColorPalette } = {
  light: {
    background: '#FFFFFF',
    surface: '#F2F5F4',
    border: '#C9D2CF',
    text: '#14201C', // ~16:1 on white
    textMuted: '#4A5753', // ~7.5:1 on white
    primary: '#1B5E4B', // white text on this is ~7.9:1
    onPrimary: '#FFFFFF',
    disabled: '#D5DBD9',
    onDisabled: '#4A5753', // ~5.5:1 on disabled
    positive: '#1B6E3A',
    negative: '#B3261E',
    warning: '#8A5300', // ~6:1 on white
    tabInactive: '#4A5753',
  },
  dark: {
    background: '#0F1513',
    surface: '#1C2421',
    border: '#3A4642',
    text: '#EEF3F1', // ~16:1 on background
    textMuted: '#B4C0BC', // ~10:1 on background
    primary: '#7FD8B9', // dark text on this is ~11:1
    onPrimary: '#0F1513',
    disabled: '#2C3532',
    onDisabled: '#B4C0BC', // ~7:1 on disabled
    positive: '#7FD89A',
    negative: '#FFB4AB',
    warning: '#FFC870', // ~12:1 on background
    tabInactive: '#B4C0BC',
  },
};

/** Spacing scale in density-independent pixels. */
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

/** Font sizes, slightly larger than platform defaults for easy reading. */
export const fontSizes = {
  small: 15,
  body: 18,
  large: 22,
  title: 30,
  money: 36,
} as const;

/** Minimum height for anything tappable (larger than the 44/48 platform minimum). */
export const minTouchSize = 56;

export const radius = {
  sm: 8,
  md: 14,
} as const;

export type Theme = {
  dark: boolean;
  colors: ColorPalette;
  spacing: typeof spacing;
  fontSizes: typeof fontSizes;
  radius: typeof radius;
  minTouchSize: number;
};

export function getTheme(scheme: 'light' | 'dark' | null | undefined): Theme {
  const dark = scheme === 'dark';
  return {
    dark,
    colors: dark ? colors.dark : colors.light,
    spacing,
    fontSizes,
    radius,
    minTouchSize,
  };
}

/** Current theme, following the phone's light/dark setting. */
export function useTheme(): Theme {
  const scheme = useColorScheme();
  return getTheme(scheme === 'dark' ? 'dark' : 'light');
}
