import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Text, useTheme, Divider, Badge } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { formatRelativeTime } from '@core/utils/format';
import type { CitizenNotification } from '../types/dashboard.types';

interface NotificationsListProps {
  notifications: CitizenNotification[];
}

const ACTION_ICONS: Record<string, string> = {
  STATUS_CHANGE: 'swap-horizontal-circle-outline',
  AGENT_ACTION: 'account-check-outline',
  COMMENT_ADDED: 'comment-text-outline',
  CITA_SCHEDULED: 'calendar-check',
  PAYMENT_RECEIVED: 'cash-check',
  VALIDATION_FAILED: 'alert-circle-outline',
};

export function NotificationsList({ notifications }: NotificationsListProps) {
  const theme = useTheme();
  const { t } = useTranslation();

  if (notifications.length === 0) {
    return (
      <View style={styles.empty}>
        <Text variant="bodyMedium" style={{ color: theme.colors.outline }}>{t('notifications.empty')}</Text>
      </View>
    );
  }

  return (
    <View>
      {notifications.map((notif, i) => (
        <React.Fragment key={notif.id}>
          <View style={[styles.item, { paddingVertical: 10, paddingHorizontal: 4 }]}>
            <View style={[styles.iconWrap, { backgroundColor: notif.is_new ? theme.colors.primaryContainer : theme.colors.surfaceVariant }]}>
              <MaterialCommunityIcons
                name={(ACTION_ICONS[notif.action] ?? 'bell-outline') as keyof typeof MaterialCommunityIcons.glyphMap}
                size={18}
                color={notif.is_new ? theme.colors.primary : theme.colors.onSurfaceVariant}
              />
            </View>
            <View style={styles.content}>
              <View style={styles.titleRow}>
                <Text variant="labelMedium" style={{ color: theme.colors.onSurface, fontWeight: notif.is_new ? '700' : '500', flex: 1 }} numberOfLines={1}>
                  {notif.title}
                </Text>
                {notif.is_new && <Badge size={8} style={{ backgroundColor: theme.colors.primary }} />}
              </View>
              {notif.message && (
                <Text variant="bodySmall" style={{ color: theme.colors.onSurfaceVariant }} numberOfLines={2}>
                  {notif.message}
                </Text>
              )}
              <Text variant="labelSmall" style={{ color: theme.colors.outline }}>
                {formatRelativeTime(notif.performed_at)}
              </Text>
            </View>
          </View>
          {i < notifications.length - 1 && <Divider />}
        </React.Fragment>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  empty: { alignItems: 'center', paddingVertical: 24 },
  item: { flexDirection: 'row', gap: 10 },
  iconWrap: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  content: { flex: 1, gap: 2 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
});
