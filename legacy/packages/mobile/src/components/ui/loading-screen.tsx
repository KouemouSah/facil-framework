/**
 * Full-screen loading indicator
 *
 * Displays a centered spinner with an optional descriptive message.
 * All colors are drawn from the app theme.
 */

import { View, StyleSheet } from 'react-native';
import { ActivityIndicator, Text } from 'react-native-paper';

import { useAppTheme } from '@core/theme';

interface LoadingScreenProps {
  /** Optional message displayed below the spinner. */
  message?: string;
}

export function LoadingScreen({ message }: LoadingScreenProps) {
  const { colors, spacing } = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <ActivityIndicator size="large" color={colors.primary} />
      {message && (
        <Text
          variant="bodyMedium"
          style={[styles.message, { color: colors.onSurface, marginTop: spacing.md }]}
        >
          {message}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  message: {
    textAlign: 'center',
  },
});
