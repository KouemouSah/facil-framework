/**
 * Standard screen wrapper
 *
 * Provides SafeAreaView insets, StatusBar handling, themed background,
 * and optional scrolling with consistent padding.
 */

import { ScrollView, View, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';

import { useAppTheme } from '@core/theme';

interface ScreenWrapperProps {
  children: React.ReactNode;
  /** Wrap children in a ScrollView. Defaults to false. */
  scrollable?: boolean;
  /** Apply horizontal and vertical padding from theme spacing. Defaults to true. */
  padded?: boolean;
  /** SafeAreaView edges to respect. Defaults to ['top', 'bottom']. */
  edges?: Edge[];
}

export function ScreenWrapper({
  children,
  scrollable = false,
  padded = true,
  edges = ['top', 'bottom'],
}: ScreenWrapperProps) {
  const { colors, spacing, isDark } = useAppTheme();

  const paddingStyle = padded ? { paddingHorizontal: spacing.md, paddingVertical: spacing.md } : undefined;

  const content = scrollable ? (
    <ScrollView
      contentContainerStyle={[styles.scrollContent, paddingStyle]}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
    >
      {children}
    </ScrollView>
  ) : (
    <View style={[styles.inner, paddingStyle]}>{children}</View>
  );

  return (
    <SafeAreaView
      edges={edges}
      style={[styles.safe, { backgroundColor: colors.background }]}
    >
      <StatusBar
        barStyle={isDark ? 'light-content' : 'dark-content'}
        backgroundColor={colors.background}
      />
      {content}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  inner: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
  },
});
