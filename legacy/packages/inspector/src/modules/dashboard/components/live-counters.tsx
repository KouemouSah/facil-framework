/**
 * Live Counters - Real-time agent status bar
 */

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@core/theme';
import type { LiveStatusCounters } from '@modules/inspections/types/inspection.types';

interface Props {
  counters: LiveStatusCounters;
}

export function LiveCounters({ counters }: Props) {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();

  const items = [
    { value: counters.active_agents, label: t('supervisor.active'), color: custom.status.conforme },
    { value: counters.idle_agents, label: t('supervisor.idle'), color: custom.status.inProgress },
    { value: counters.offline_agents, label: t('supervisor.offline'), color: custom.status.cancelled },
    { value: counters.inspections_today, label: t('dashboard.todayStats'), color: colors.primary },
  ];

  return (
    <Pressable
      onPress={() => router.push('/supervisor/agents' as never)}
      style={[styles.container, { backgroundColor: colors.surface }]}
      android_ripple={{ color: colors.surfaceVariant }}
    >
      {items.map((item, i) => (
        <View key={i} style={styles.counterItem}>
          <View style={[styles.dot, { backgroundColor: item.color }]} />
          <Text variant="titleMedium" style={{ color: item.color, fontWeight: '700' }}>
            {item.value}
          </Text>
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
            {item.label}
          </Text>
        </View>
      ))}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    marginHorizontal: 16,
    borderRadius: 8,
    paddingVertical: 12,
    marginBottom: 16,
  },
  counterItem: { flex: 1, alignItems: 'center', gap: 2 },
  dot: { width: 8, height: 8, borderRadius: 4, marginBottom: 2 },
});
