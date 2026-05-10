/**
 * Recent Inspections — Flat list with section header, status icons, chevron
 * Android native: 56dp rows, dots, dividers, ripple effect
 */

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Divider, Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useAppTheme } from '@core/theme';
import { formatDate } from '@core/utils/format';
import type { InspectionListItem } from '@modules/inspections/types/inspection.types';

interface Props {
  items: InspectionListItem[];
  title?: string;
}

const STATUS_ICONS: Record<string, { icon: string }> = {
  in_progress: { icon: 'progress-clock' },
  completed: { icon: 'check-circle' },
  conforme: { icon: 'check-circle' },
  non_conforme: { icon: 'alert-circle' },
  mise_en_demeure: { icon: 'alert-octagon' },
  seal_proposed: { icon: 'shield-alert' },
  seal_approved: { icon: 'lock' },
  seal_rejected: { icon: 'shield-off' },
  cancelled: { icon: 'close-circle' },
  pending: { icon: 'clock-outline' },
};

export function RecentInspections({ items, title }: Props) {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();

  const STATUS_COLORS: Record<string, string> = {
    in_progress: custom.status.inProgress,
    completed: custom.status.completed,
    conforme: custom.status.conforme,
    non_conforme: custom.status.nonConforme,
    mise_en_demeure: custom.status.miseEnDemeure,
    seal_proposed: custom.status.sealProposed,
    seal_approved: custom.status.sealApproved,
    seal_rejected: custom.status.sealRejected,
    cancelled: custom.status.cancelled,
    pending: custom.status.inProgress,
  };

  if (items.length === 0) {
    return (
      <View style={styles.empty}>
        <MaterialCommunityIcons name="clipboard-text-outline" size={36} color={colors.onSurfaceVariant} style={{ opacity: 0.4 }} />
        <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, marginTop: 8 }}>
          {t('dashboard.noRecent')}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {title && (
        <View style={[styles.sectionHeader, { backgroundColor: colors.background }]}>
          <Text variant="labelLarge" style={{ color: colors.onSurfaceVariant, fontWeight: '600' }}>
            {title}
          </Text>
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
            {items.length}
          </Text>
        </View>
      )}
      <View style={[styles.listContainer, { backgroundColor: colors.surface }]}>
        {items.map((item, index) => {
          const statusKey = item.result ?? item.status;
          const dotColor = STATUS_COLORS[statusKey] ?? colors.onSurfaceVariant;
          const iconName = STATUS_ICONS[statusKey]?.icon ?? 'circle';

          return (
            <React.Fragment key={item.id}>
              <Pressable
                onPress={() => router.push(`/inspection/${item.id}` as never)}
                style={({ pressed }) => [
                  styles.item,
                  pressed && { backgroundColor: colors.surfaceVariant },
                ]}
                android_ripple={{ color: colors.surfaceVariant }}
              >
                <MaterialCommunityIcons
                  name={iconName as never}
                  size={20}
                  color={dotColor}
                  style={styles.statusIcon}
                />
                <View style={styles.itemBody}>
                  <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '500' }} numberOfLines={1}>
                    {item.company_name ?? item.company_nif ?? '-'}
                  </Text>
                  <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                    {formatDate(item.inspection_date)} {item.entity_code ? `\u2022 ${item.entity_code}` : ''}
                  </Text>
                </View>
                <View style={styles.itemRight}>
                  <Text variant="labelSmall" style={{ color: dotColor, fontWeight: '600' }}>
                    {t(`${item.result ? 'result' : 'status'}.${item.result ?? item.status}`)}
                  </Text>
                  {(item.payment_collected || item.mise_en_demeure_issued || item.seal_applied) && (
                    <View style={styles.badges}>
                      {item.payment_collected && <MaterialCommunityIcons name="cash-check" size={12} color={colors.primary} />}
                      {item.mise_en_demeure_issued && <MaterialCommunityIcons name="alert-circle" size={12} color={custom.status.miseEnDemeure} />}
                      {item.seal_applied && <MaterialCommunityIcons name="lock" size={12} color={custom.status.sealApproved} />}
                    </View>
                  )}
                </View>
                <MaterialCommunityIcons name="chevron-right" size={18} color={colors.onSurfaceVariant} style={{ marginLeft: 4 }} />
              </Pressable>
              {index < items.length - 1 && <Divider style={{ marginLeft: 48 }} />}
            </React.Fragment>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {},
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  listContainer: {
    marginHorizontal: 12,
    borderRadius: 12,
    overflow: 'hidden',
  },
  empty: { padding: 40, alignItems: 'center' },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    height: 60,
  },
  statusIcon: { marginRight: 12 },
  itemBody: { flex: 1, justifyContent: 'center' },
  itemRight: { alignItems: 'flex-end', marginLeft: 8 },
  badges: { flexDirection: 'row', gap: 4, marginTop: 2 },
});
