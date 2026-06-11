import React from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { Surface, Text, useTheme } from 'react-native-paper';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import type { DashboardActionRequired } from '../types/dashboard.types';

interface ActionRequiredBannerProps {
  actions: DashboardActionRequired[];
}

export function ActionRequiredBanner({ actions }: ActionRequiredBannerProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const router = useRouter();

  if (actions.length === 0) return null;

  return (
    <Surface style={[styles.banner, { backgroundColor: theme.colors.errorContainer, borderRadius: 12 }]} elevation={0}>
      <View style={styles.header}>
        <MaterialCommunityIcons name="alert-circle" size={20} color={theme.colors.error} />
        <Text variant="titleSmall" style={{ color: theme.colors.error, fontWeight: '600', marginLeft: 8 }}>
          {t('dashboard.actionRequired')} ({actions.length})
        </Text>
      </View>
      {actions.map((action) => (
        <Pressable
          key={action.request_id}
          style={styles.actionItem}
          onPress={() => router.push(`/(tabs)/requests/${action.request_id}`)}
        >
          <Text variant="bodySmall" style={{ color: theme.colors.onErrorContainer, flex: 1 }} numberOfLines={2}>
            {action.message}
          </Text>
          <MaterialCommunityIcons name="chevron-right" size={16} color={theme.colors.onErrorContainer} />
        </Pressable>
      ))}
    </Surface>
  );
}

const styles = StyleSheet.create({
  banner: { padding: 16 },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  actionItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, gap: 8 },
});
