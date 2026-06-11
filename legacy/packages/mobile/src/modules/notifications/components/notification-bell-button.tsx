/**
 * Bell icon with an unread count badge.
 * Tapping it opens the Notification Center stack route.
 */

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';

import { useAppTheme } from '@core/theme';
import { useNotificationBadge } from '@modules/notifications/hooks/use-notification-badge';

interface NotificationBellButtonProps {
  /** Override icon color (defaults to theme onSurface). */
  color?: string;
  /** Icon size in pixels. */
  size?: number;
}

export function NotificationBellButton({
  color,
  size = 24,
}: NotificationBellButtonProps) {
  const { colors } = useAppTheme();
  const unread = useNotificationBadge();
  const iconColor = color ?? colors.onSurface;
  const display = unread > 99 ? '99+' : String(unread);

  return (
    <Pressable
      onPress={() => router.push('/notifications')}
      android_ripple={{ color: colors.surfaceVariant, borderless: true, radius: 24 }}
      style={styles.button}
      accessibilityLabel="Notifications"
      hitSlop={8}
    >
      <MaterialCommunityIcons name="bell-outline" size={size} color={iconColor} />
      {unread > 0 ? (
        <View style={[styles.badge, { backgroundColor: colors.error }]}>
          <Text style={styles.badgeText} numberOfLines={1}>
            {display}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badge: {
    position: 'absolute',
    top: 4,
    right: 4,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    paddingHorizontal: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: 'white',
    fontSize: 10,
    fontWeight: '700',
  },
});
