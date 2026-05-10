/**
 * Empty state placeholder
 *
 * Shown when a list or section has no data. Displays an icon, a title,
 * an optional description, and an optional action button.
 */

import { View, StyleSheet } from 'react-native';
import { Text, Button } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';

interface EmptyStateProps {
  /** MaterialCommunityIcons name (e.g. "folder-open-outline"). */
  icon: string;
  /** Primary message. */
  title: string;
  /** Secondary explanatory text. */
  description?: string;
  /** Label for the optional CTA button. */
  actionLabel?: string;
  /** Handler for the optional CTA button. */
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  const { colors, spacing } = useAppTheme();

  return (
    <View style={[styles.container, { padding: spacing.xl }]}>
      <MaterialCommunityIcons
        name={icon as React.ComponentProps<typeof MaterialCommunityIcons>['name']}
        size={64}
        color={colors.onSurfaceVariant}
        style={{ marginBottom: spacing.md }}
      />

      <Text
        variant="titleMedium"
        style={[styles.title, { color: colors.onSurface, marginBottom: spacing.xs }]}
      >
        {title}
      </Text>

      {description && (
        <Text
          variant="bodyMedium"
          style={[
            styles.description,
            { color: colors.onSurfaceVariant, marginBottom: spacing.md },
          ]}
        >
          {description}
        </Text>
      )}

      {actionLabel && onAction && (
        <Button mode="contained" onPress={onAction} style={{ marginTop: spacing.sm }}>
          {actionLabel}
        </Button>
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
  title: {
    textAlign: 'center',
  },
  description: {
    textAlign: 'center',
  },
});
