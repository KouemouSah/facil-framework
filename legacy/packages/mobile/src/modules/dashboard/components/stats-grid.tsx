import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Card, Text, useTheme } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { formatCurrency } from '@core/utils/format';
import type { DashboardStats } from '../types/dashboard.types';

interface StatsGridProps {
  stats: DashboardStats;
}

export function StatsGrid({ stats }: StatsGridProps) {
  const theme = useTheme();
  const { t } = useTranslation();

  const items = [
    { label: t('dashboard.stats.active'), value: String(stats.active), icon: 'file-clock-outline', color: theme.colors.tertiary },
    { label: t('dashboard.stats.completed'), value: String(stats.completed), icon: 'check-circle-outline', color: theme.colors.primary },
    { label: t('dashboard.stats.pendingAction'), value: String(stats.pending_action), icon: 'alert-circle-outline', color: theme.colors.error },
    { label: t('dashboard.stats.totalPaid'), value: formatCurrency(stats.total_paid), icon: 'cash-multiple', color: theme.colors.primary },
  ];

  return (
    <View style={styles.grid}>
      {items.map((item) => (
        <Card key={item.label} style={[styles.card, { backgroundColor: theme.colors.surface }]}>
          <Card.Content style={styles.cardContent}>
            <MaterialCommunityIcons name={item.icon as keyof typeof MaterialCommunityIcons.glyphMap} size={24} color={item.color} />
            <Text variant="titleLarge" style={[styles.value, { color: theme.colors.onSurface }]}>{item.value}</Text>
            <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }} numberOfLines={1}>{item.label}</Text>
          </Card.Content>
        </Card>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  card: { flex: 1, minWidth: '47%', borderRadius: 12 },
  cardContent: { alignItems: 'flex-start', padding: 12, gap: 4 },
  value: { fontWeight: '700' },
});
