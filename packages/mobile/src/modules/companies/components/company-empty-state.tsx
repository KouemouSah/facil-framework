import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

interface CompanyEmptyStateProps {
  onCreate?: () => void;
}

export function CompanyEmptyState({ onCreate }: CompanyEmptyStateProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <View style={styles.container}>
      <MaterialCommunityIcons
        name="domain-plus"
        size={56}
        color={colors.onSurfaceVariant}
      />
      <Text variant="titleMedium" style={[styles.title, { color: colors.onSurface }]}>
        {t('companies.empty.title')}
      </Text>
      <Text variant="bodySmall" style={[styles.body, { color: colors.onSurfaceVariant }]}>
        {t('companies.empty.body')}
      </Text>
      {onCreate ? (
        <Button mode="contained" onPress={onCreate} style={styles.button}>
          {t('companies.empty.cta')}
        </Button>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', paddingVertical: 64, paddingHorizontal: 24 },
  title: { marginTop: 16, textAlign: 'center' },
  body: { marginTop: 8, textAlign: 'center' },
  button: { marginTop: 24 },
});
