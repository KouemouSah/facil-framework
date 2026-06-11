/**
 * Theme Provider - Facil Inspeccion
 *
 * Material Design 3 theme with blue professional palette.
 */

import React, { createContext, useContext, useMemo } from 'react';
import { useColorScheme } from 'react-native';
import {
  MD3DarkTheme,
  MD3LightTheme,
  PaperProvider,
  type MD3Theme,
} from 'react-native-paper';
import { inspectorColors, inspectorColorsDark } from './colors';

// Use deep-string type to allow different literal values between light/dark
type DeepString<T> = T extends string ? string : { [K in keyof T]: DeepString<T[K]> };
type InspectorColors = DeepString<typeof inspectorColors>;

interface AppTheme extends MD3Theme {
  custom: InspectorColors;
}

const lightTheme: AppTheme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: inspectorColors.primary.main,
    primaryContainer: inspectorColors.primary.container,
    secondary: inspectorColors.secondary.main,
    secondaryContainer: inspectorColors.secondary.container,
    background: inspectorColors.background,
    surface: inspectorColors.surface,
    surfaceVariant: inspectorColors.surfaceVariant,
    error: inspectorColors.error,
    onPrimary: inspectorColors.primary.contrast,
    onBackground: inspectorColors.text.primary,
    onSurface: inspectorColors.text.primary,
    onSurfaceVariant: inspectorColors.text.secondary,
    outline: inspectorColors.divider,
  },
  custom: inspectorColors,
};

const darkTheme: AppTheme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: inspectorColorsDark.primary.main,
    primaryContainer: inspectorColorsDark.primary.container,
    secondary: inspectorColorsDark.secondary.main,
    background: inspectorColorsDark.background,
    surface: inspectorColorsDark.surface,
    surfaceVariant: inspectorColorsDark.surfaceVariant,
    error: inspectorColorsDark.error,
    onPrimary: inspectorColorsDark.primary.contrast,
    onBackground: inspectorColorsDark.text.primary,
    onSurface: inspectorColorsDark.text.primary,
    onSurfaceVariant: inspectorColorsDark.text.secondary,
    outline: inspectorColorsDark.divider,
  },
  custom: inspectorColorsDark,
};

const ThemeContext = createContext<AppTheme>(lightTheme);

export function useAppTheme(): AppTheme {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const colorScheme = useColorScheme();
  const theme = useMemo(
    () => (colorScheme === 'dark' ? darkTheme : lightTheme),
    [colorScheme],
  );

  return (
    <ThemeContext.Provider value={theme}>
      <PaperProvider theme={theme}>{children}</PaperProvider>
    </ThemeContext.Provider>
  );
}
