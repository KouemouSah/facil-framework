import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

interface DocumentEmptyStateProps {
  variant?: 'uploads' | 'generated' | 'alerts';
  onUpload?: () => void;
}

export function DocumentEmptyState({
  variant = 'uploads',
  onUpload,
}: DocumentEmptyStateProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const iconName =
    variant === 'alerts'
      ? 'bell-off-outline'
      : variant === 'generated'
        ? 'file-document-outline'
        : 'folder-open-outline';

  return (
    <View style={styles.container}>
      <MaterialCommunityIcons
        name={iconName}
        size={56}
        color={colors.onSurfaceVariant}
      />
      <Text variant="titleMedium" style={[styles.title, { color: colors.onSurface }]}>
        {t(`vault.empty.${variant}.title`)}
      </Text>
      <Text variant="bodySmall" style={[styles.body, { color: colors.onSurfaceVariant }]}>
        {t(`vault.empty.${variant}.body`)}
      </Text>
      {variant === 'uploads' && onUpload ? (
        <Button mode="contained" onPress={onUpload} style={styles.button}>
          {t('vault.empty.uploads.cta')}
        </Button>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  // Top-aligned (paddingTop only) so the empty state sits right under the
  // filter chips instead of vertical-centering in the FlatList area. The
  // "centered" look (paddingVertical: 64) was visually disconnected from the
  // chips bar above (see debug/tesoro/m6.jpg).
  container: {
    alignItems: 'center',
    paddingTop: 48,
    paddingBottom: 24,
    paddingHorizontal: 24,
  },
  title: {
    marginTop: 16,
    textAlign: 'center',
  },
  body: {
    marginTop: 8,
    textAlign: 'center',
  },
  button: {
    marginTop: 24,
  },
});
