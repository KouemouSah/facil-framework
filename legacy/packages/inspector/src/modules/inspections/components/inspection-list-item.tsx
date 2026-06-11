import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { formatDate } from '@core/utils/format';
import type { InspectionListItem as ListItemType } from '@modules/inspections/types/inspection.types';

interface Props {
  item: ListItemType;
}

export const InspectionListItemRow = React.memo(function InspectionListItemRow({ item }: Props) {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();

  const STATUS_DOT: Record<string, string> = {
    in_progress: custom.status.inProgress,
    completed: custom.status.completed,
    mise_en_demeure: custom.status.miseEnDemeure,
    seal_proposed: custom.status.sealProposed,
    seal_approved: custom.status.sealApproved,
    seal_rejected: custom.status.sealRejected,
    cancelled: custom.status.cancelled,
    conforme: custom.status.conforme,
    non_conforme: custom.status.nonConforme,
    pending: custom.status.inProgress,
  };

  const dotKey = item.result ?? item.status;
  const dotColor = STATUS_DOT[dotKey] ?? custom.secondary.main;
  const labelKey = item.result ? `result.${item.result}` : `status.${item.status}`;

  return (
    <Pressable
      onPress={() => router.push(`/inspection/${item.id}` as never)}
      style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surfaceVariant }]}
      android_ripple={{ color: colors.surfaceVariant }}
    >
      <View style={[styles.dot, { backgroundColor: dotColor }]} />
      <View style={styles.body}>
        <Text variant="bodyMedium" style={{ color: colors.onSurface }} numberOfLines={1}>
          {item.company_name ?? item.company_nif ?? '—'}
        </Text>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }} numberOfLines={1}>
          {formatDate(item.inspection_date)} • {item.entity_code ?? ''}
        </Text>
      </View>
      <View style={styles.right}>
        <Text variant="labelSmall" style={{ color: dotColor }}>
          {t(labelKey)}
        </Text>
        <View style={styles.icons}>
          {item.payment_collected && (
            <MaterialCommunityIcons name="cash-check" size={14} color={colors.primary} />
          )}
          {item.mise_en_demeure_issued && (
            <MaterialCommunityIcons name="alert-circle" size={14} color={custom.status.miseEnDemeure} />
          )}
          {item.seal_applied && (
            <MaterialCommunityIcons name="lock" size={14} color={custom.status.sealApproved} />
          )}
        </View>
      </View>
    </Pressable>
  );
});

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', height: 64, paddingHorizontal: 16 },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  body: { flex: 1, justifyContent: 'center' },
  right: { alignItems: 'flex-end', marginLeft: 8 },
  icons: { flexDirection: 'row', gap: 4, marginTop: 2 },
});
