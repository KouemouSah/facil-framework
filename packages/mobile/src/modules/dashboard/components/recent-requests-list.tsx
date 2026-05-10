import React from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { Text, useTheme, Divider } from 'react-native-paper';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { formatRelativeTime, formatCurrency } from '@core/utils/format';
import type { DashboardRecentRequest } from '../types/dashboard.types';

interface RecentRequestsListProps {
  requests: DashboardRecentRequest[];
}

export function RecentRequestsList({ requests }: RecentRequestsListProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const router = useRouter();

  if (requests.length === 0) {
    return (
      <View style={styles.empty}>
        <Text variant="bodyMedium" style={{ color: theme.colors.outline }}>{t('dashboard.emptyRequests')}</Text>
      </View>
    );
  }

  return (
    <View>
      {requests.map((req, i) => (
        <React.Fragment key={req.id}>
          <Pressable
            style={[styles.item, { paddingVertical: 12, paddingHorizontal: 4 }]}
            onPress={() => router.push(`/(tabs)/requests/${req.id}`)}
            android_ripple={{ color: theme.colors.primaryContainer }}
          >
            <View style={styles.itemContent}>
              <Text variant="titleSmall" style={{ color: theme.colors.onSurface, fontWeight: '600' }} numberOfLines={1}>
                {req.workflow_label}
              </Text>
              <Text variant="bodySmall" style={{ color: theme.colors.outline }}>
                {req.reference} · {formatRelativeTime(req.created_at)}
              </Text>
            </View>
            <View style={styles.itemRight}>
              {req.total_amount != null && req.total_amount > 0 && (
                <Text variant="labelMedium" style={{ color: theme.colors.onSurface, fontWeight: '600' }}>
                  {formatCurrency(req.total_amount)}
                </Text>
              )}
              <MaterialCommunityIcons name="chevron-right" size={20} color={theme.colors.outline} />
            </View>
          </Pressable>
          {i < requests.length - 1 && <Divider />}
        </React.Fragment>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  empty: { alignItems: 'center', paddingVertical: 24 },
  item: { flexDirection: 'row', alignItems: 'center' },
  itemContent: { flex: 1, gap: 2 },
  itemRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
