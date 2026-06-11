/**
 * Facil Mobile — Theme Provider
 *
 * Combines react-native-paper MD3 theming with custom color, typography,
 * and spacing tokens. Exposes:
 * - <ThemeProvider> — wrap at app root
 * - useAppTheme()  — typed hook for consuming theme in components
 *
 * Uses the system color scheme by default; override via ThemeProvider props
 * if a user-level setting is needed later.
 */

import React, { createContext, useContext, useMemo } from 'react';
import { useColorScheme } from 'react-native';
import {
  MD3LightTheme,
  MD3DarkTheme,
  PaperProvider,
} from 'react-native-paper';

import { colors } from './colors';
import { typography } from './typography';
import { spacing, borderRadius } from './spacing';

// ---------------------------------------------------------------------------
// Theme construction
// ---------------------------------------------------------------------------

const lightTheme = {
  ...MD3LightTheme,
  colors: { ...MD3LightTheme.colors, ...colors.light },
} as const;

const darkTheme = {
  ...MD3DarkTheme,
  colors: { ...MD3DarkTheme.colors, ...colors.dark },
} as const;

// ---------------------------------------------------------------------------
// Extended theme type (MD3 + custom tokens)
// ---------------------------------------------------------------------------

/** Light or dark Paper theme (union of both for type compatibility). */
type PaperTheme = typeof lightTheme | typeof darkTheme;

/** Light or dark color token set. */
type ColorTokens = typeof colors.light | typeof colors.dark;

/**
 * The full theme object available via useAppTheme().
 * Includes Paper's MD3 theme plus custom spacing, typography, and borderRadius.
 */
export interface AppTheme {
  /** react-native-paper MD3 theme (light or dark) */
  paper: PaperTheme;
  /** Custom color tokens (includes semantic status colors) */
  colors: ColorTokens;
  /** MD3 type scale */
  typography: typeof typography;
  /** Spacing grid tokens */
  spacing: typeof spacing;
  /** Border-radius tokens */
  borderRadius: typeof borderRadius;
  /** Whether the current scheme is dark */
  isDark: boolean;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AppThemeContext = createContext<AppTheme | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface ThemeProviderProps {
  children: React.ReactNode;
  /** Force a specific color scheme instead of using the system setting. */
  forcedColorScheme?: 'light' | 'dark';
}

/**
 * Wrap the app root with <ThemeProvider> to provide both react-native-paper
 * and custom theme tokens to the entire tree.
 *
 * ```tsx
 * <ThemeProvider>
 *   <App />
 * </ThemeProvider>
 * ```
 */
export function ThemeProvider({ children, forcedColorScheme }: ThemeProviderProps) {
  const systemScheme = useColorScheme();
  const isDark = forcedColorScheme
    ? forcedColorScheme === 'dark'
    : systemScheme === 'dark';

  const paperTheme = isDark ? darkTheme : lightTheme;
  const colorTokens = isDark ? colors.dark : colors.light;

  const appTheme = useMemo<AppTheme>(
    () => ({
      paper: paperTheme,
      colors: colorTokens,
      typography,
      spacing,
      borderRadius,
      isDark,
    }),
    [isDark, paperTheme, colorTokens],
  );

  return (
    <AppThemeContext.Provider value={appTheme}>
      <PaperProvider theme={paperTheme}>{children}</PaperProvider>
    </AppThemeContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access the current app theme (colors, typography, spacing, borderRadius).
 *
 * Must be used inside a <ThemeProvider>.
 *
 * ```tsx
 * const { colors, spacing, typography } = useAppTheme();
 * ```
 */
export function useAppTheme(): AppTheme {
  const theme = useContext(AppThemeContext);
  if (!theme) {
    throw new Error('useAppTheme must be used within a <ThemeProvider>');
  }
  return theme;
}

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { colors } from './colors';
export { typography } from './typography';
export { spacing, borderRadius } from './spacing';
export type { SemanticColor, ColorScheme } from './colors';
export type { TypographyVariant } from './typography';
export type { SpacingKey, BorderRadiusKey } from './spacing';
