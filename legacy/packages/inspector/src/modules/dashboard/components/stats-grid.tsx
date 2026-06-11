/**
 * Stats Grid — Material Design 3 KPI cards
 * 2x2 grid with colored accents and compact layout.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import type { InspectionStats } from '@modules/inspections/types/inspection.types';

interface Props {
  stats: InspectionStats;
  label: string;
}

export function StatsGrid({ stats, label }: Props) {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();

  const items = [
    { value: String(stats.total), label: t('dashboard.total'), color: colors.primary, icon: 'clipboard-check-outline' },
    { value: String(stats.conforme), label: t('dashboard.conforme'), color: custom.status.conforme, icon: 'check-circle-outline' },
    { value: String(stats.non_conforme), label: t('dashboard.nonConforme'), color: custom.status.nonConforme, icon: 'alert-circle-outline' },
    { value: formatCurrency(stats.total_collected_amount), label: t('dashboard.collected'), color: custom.tertiary.main, icon: 'cash' },
  ];

  return (
    <View style={styles.container}>
      <Text variant="labelLarge" style={[styles.sectionLabel, { color: colors.onSurfaceVariant }]}>
        {label}
      </Text>
      <View style={styles.grid}>
        {items.map((item, i) => (
          <View
            key={i}
            style={[
              styles.card,
              {
                backgroundColor: colors.surface,
                borderLeftColor: item.color,
              },
            ]}
          >
            <View style={styles.cardHeader}>
              <MaterialCommunityIcons name={item.icon as never} size={16} color={item.color} />
              <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant, marginLeft: 4 }}>
                {item.label}
              </Text>
            </View>
            <Text variant="headlineSmall" style={{ color: item.color, fontWeight: '700' }}>
              {item.value}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 16 },
  sectionLabel: { paddingHorizontal: 16, paddingBottom: 8, fontWeight: '600' },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    gap: 8,
  },
  card: {
    width: '47%' as unknown as number,
    borderRadius: 8,
    borderLeftWidth: 3,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
});
