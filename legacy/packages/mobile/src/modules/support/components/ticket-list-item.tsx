import { memo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { formatRelativeTime } from '@core/utils/format';
import type { SupportTicket, TicketStatus } from '../types/support.types';

interface Props {
  item: SupportTicket;
  /** Receives the ticket id — keep stable (useCallback) for `memo` to work. */
  onPress: (ticketId: number) => void;
}

function getStatusDotColor(status: TicketStatus, isDark: boolean): string {
  switch (status) {
    case 'open':
      return isDark ? '#42A5F5' : '#1565C0';
    case 'in_progress':
      return isDark ? '#FFA726' : '#FF9800';
    case 'pending_user':
      return isDark ? '#FFCA28' : '#FFC107';
    case 'resolved':
      return isDark ? '#66BB6A' : '#1B5E20';
    case 'closed':
      return isDark ? '#BDBDBD' : '#9E9E9E';
    default:
      return isDark ? '#BDBDBD' : '#9E9E9E';
  }
}

function getStatusTextColor(status: TicketStatus, isDark: boolean): string {
  if (isDark) {
    switch (status) {
      case 'open':
        return '#90CAF9';
      case 'in_progress':
        return '#FFB74D';
      case 'pending_user':
        return '#FFCC80';
      case 'resolved':
        return '#A5D6A7';
      case 'closed':
        return '#BDBDBD';
    }
  }
  switch (status) {
    case 'open':
      return '#0D3D6B';
    case 'in_progress':
      return '#7A2E00';
    case 'pending_user':
      return '#7A4F00';
    case 'resolved':
      return '#1B5E20';
    case 'closed':
      return '#616161';
  }
}

function TicketListItemImpl({ item, onPress }: Props) {
  const { colors, spacing, isDark } = useAppTheme();
  const { t } = useTranslation();

  const dotColor = getStatusDotColor(item.status, isDark);
  const statusColor = getStatusTextColor(item.status, isDark);
  const statusLabel = t(`support.status.${item.status}`, { defaultValue: item.status });
  const timeAgo = formatRelativeTime(item.updated_at || item.created_at);

  const a11yLabel = t('support.a11y.item', {
    subject: item.subject,
    status: statusLabel,
    number: item.ticket_number,
    defaultValue: `${item.subject}, ${statusLabel}, ${item.ticket_number}`,
  });

  return (
    <Pressable
      onPress={() => onPress(item.id)}
      android_ripple={{ color: colors.primaryContainer }}
      accessibilityRole="button"
      accessibilityLabel={a11yLabel}
      style={[
        styles.container,
        { paddingHorizontal: spacing.md, paddingVertical: 12 },
      ]}
    >
      <View style={[styles.dot, { backgroundColor: dotColor }]} />

      <View style={styles.content}>
        <View style={styles.line1}>
          <Text
            variant="bodyLarge"
            style={[styles.title, { color: colors.onSurface }]}
            numberOfLines={1}
          >
            {item.subject}
          </Text>
          <Text style={[styles.statusText, { color: statusColor }]} numberOfLines={1}>
            {statusLabel}
          </Text>
        </View>
        <View style={styles.line2}>
          <Text
            variant="bodySmall"
            style={{ color: colors.outline, flex: 1 }}
            numberOfLines={1}
          >
            {item.ticket_number} · {timeAgo}
          </Text>
          {item.message_count > 0 ? (
            <Text style={[styles.count, { color: colors.outline }]}>
              {t('support.list.messages', { count: item.message_count })}
            </Text>
          ) : null}
        </View>
      </View>

      <MaterialCommunityIcons
        name="chevron-right"
        size={20}
        color={colors.outline}
        style={{ marginLeft: 4 }}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center' },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  content: { flex: 1, gap: 2 },
  line1: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  title: { fontWeight: '600', flex: 1, fontSize: 15 },
  statusText: { fontSize: 12, fontWeight: '600' },
  line2: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  count: { fontSize: 12, marginLeft: 8 },
});

export const TicketListItem = memo(TicketListItemImpl);
