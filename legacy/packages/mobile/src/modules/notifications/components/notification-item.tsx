/**
 * NotificationItem — flat list row for the inbox screen.
 *
 * Native Android styling per memory feedback: 64dp item, leading dot color
 * indicates the channel, divider between rows, ripple on press.
 */

import React, { memo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { useAppTheme } from '@core/theme';
import type { NotificationChannelId, StoredNotification } from '@core/notifications';

interface NotificationItemProps {
  notification: StoredNotification;
  onPress: (notification: StoredNotification) => void;
  onLongPress?: (notification: StoredNotification) => void;
}

const CHANNEL_DOT_COLOR: Record<NotificationChannelId, string> = {
  default: '#9E9E9E',
  payment: '#1565C0',
  agent_decision: '#7B1FA2',
  appointment: '#388E3C',
  support: '#F57C00',
  documents: '#5D4037',
};

function formatRelative(epoch: number, locale: string): string {
  const diff = Date.now() - epoch;
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(epoch).toLocaleDateString(locale);
}

function NotificationItemImpl({
  notification,
  onPress,
  onLongPress,
}: NotificationItemProps) {
  const { colors } = useAppTheme();
  const isUnread = notification.readAt === null;
  const dotColor = CHANNEL_DOT_COLOR[notification.channelId] ?? CHANNEL_DOT_COLOR.default;

  return (
    <Pressable
      onPress={() => onPress(notification)}
      onLongPress={onLongPress ? () => onLongPress(notification) : undefined}
      android_ripple={{ color: colors.surfaceVariant }}
      style={[
        styles.row,
        { backgroundColor: isUnread ? colors.surfaceVariant : colors.surface },
      ]}
    >
      <View style={[styles.dot, { backgroundColor: dotColor }]} />
      <View style={styles.body}>
        <View style={styles.headerLine}>
          <Text
            variant="titleSmall"
            numberOfLines={1}
            style={[
              styles.title,
              { color: colors.onSurface, fontWeight: isUnread ? '700' : '500' },
            ]}
          >
            {notification.title || '—'}
          </Text>
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
            {formatRelative(notification.receivedAt, 'es')}
          </Text>
        </View>
        <Text
          variant="bodySmall"
          numberOfLines={2}
          style={{ color: colors.onSurfaceVariant }}
        >
          {notification.body}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 64,
    alignItems: 'center',
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 14,
  },
  body: {
    flex: 1,
  },
  headerLine: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  title: {
    flex: 1,
    marginRight: 8,
  },
});

/**
 * Memoized — the inbox FlatList re-renders on every refresh and badge update.
 * Reference equality on the `onPress`/`onLongPress` callbacks (parent must
 * use `useCallback`) is enough to skip rerenders for unchanged rows.
 */
export const NotificationItem = memo(NotificationItemImpl);
