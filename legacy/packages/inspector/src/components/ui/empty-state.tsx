import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useAppTheme } from '@core/theme';

interface Props {
  icon?: string;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ icon = 'clipboard-text-outline', title, description, actionLabel, onAction }: Props) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.container}>
      <MaterialCommunityIcons name={icon as any} size={64} color={colors.onSurfaceVariant} />
      <Text variant="titleMedium" style={[styles.title, { color: colors.onBackground }]}>{title}</Text>
      {description && (
        <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, textAlign: 'center' }}>
          {description}
        </Text>
      )}
      {actionLabel && onAction && (
        <Button mode="contained" onPress={onAction} style={styles.button}>{actionLabel}</Button>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32, gap: 12 },
  title: { marginTop: 8 },
  button: { marginTop: 16 },
});
