/**
 * Notification Center screen — inbox of pushes received by the device.
 *
 * Stack route (not a tab) — kept off the bottom bar to preserve the 5-tab
 * native Android pattern. Reachable via the bell icon in the dashboard header
 * or via deep link `facil://notifications`.
 */

import React, { useCallback, useEffect } from 'react';
import { FlatList, StyleSheet } from 'react-native';
import { Appbar, Divider, Menu } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import {
  type StoredNotification,
  routeFromPayload,
} from '@core/notifications';
import { useNotifications } from '@modules/notifications/hooks/use-notifications';
import { useDeviceTokenRegistration } from '@modules/notifications/hooks/use-device-token-registration';
import { useServerNotificationsSync } from '@modules/notifications/hooks/use-server-notifications-sync';
import { NotificationItem } from '@modules/notifications/components/notification-item';
import { NotificationEmptyState } from '@modules/notifications/components/notification-empty-state';
import { NotificationPermissionsBanner } from '@modules/notifications/components/notification-permissions-banner';

export default function NotificationsScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { notifications, unreadCount, markAsRead, markAllAsRead, remove, refresh } =
    useNotifications();
  const { permission, promptPermission } = useDeviceTokenRegistration();
  const { isSyncing, sync } = useServerNotificationsSync();
  const [menuVisible, setMenuVisible] = React.useState(false);

  // Pull the server audit trail at mount + after explicit refresh. Idempotent
  // (dedupes by notif id in MMKV). Runs in the background; failures are silent
  // — local MMKV remains usable.
  useEffect(() => {
    void sync().then(() => refresh());
  }, [sync, refresh]);

  const handleRefresh = useCallback(async () => {
    await sync();
    refresh();
  }, [sync, refresh]);

  const handleItemPress = useCallback(
    (notif: StoredNotification) => {
      markAsRead(notif.id);
      routeFromPayload(notif.data);
    },
    [markAsRead],
  );

  const handleItemLongPress = useCallback(
    (notif: StoredNotification) => {
      remove(notif.id);
    },
    [remove],
  );

  const showPermissionBanner = permission === 'denied' || permission === 'undetermined';

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      <Appbar.Header style={{ backgroundColor: colors.surface }}>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content
          title={t('notifications.title')}
          subtitle={
            unreadCount > 0
              ? t('notifications.unreadCount', { count: unreadCount })
              : undefined
          }
        />
        <Menu
          visible={menuVisible}
          onDismiss={() => setMenuVisible(false)}
          anchor={
            <Appbar.Action
              icon="dots-vertical"
              onPress={() => setMenuVisible(true)}
              accessibilityLabel={t('common.actions')}
            />
          }
        >
          <Menu.Item
            onPress={() => {
              setMenuVisible(false);
              markAllAsRead();
            }}
            leadingIcon="check-all"
            title={t('notifications.actions.markAllRead')}
            disabled={unreadCount === 0}
          />
        </Menu>
      </Appbar.Header>

      {showPermissionBanner ? (
        <NotificationPermissionsBanner
          onPromptAgain={permission === 'undetermined' ? promptPermission : undefined}
          needsSystemSettings={permission === 'denied'}
        />
      ) : null}

      <FlatList
        data={notifications}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <NotificationItem
            notification={item}
            onPress={handleItemPress}
            onLongPress={handleItemLongPress}
          />
        )}
        ItemSeparatorComponent={() => <Divider />}
        ListEmptyComponent={<NotificationEmptyState />}
        contentContainerStyle={notifications.length === 0 ? styles.emptyContent : undefined}
        onRefresh={handleRefresh}
        refreshing={isSyncing}
        // P8.3 — perf knobs (NotificationItem may grow with multi-line, no getItemLayout).
        initialNumToRender={15}
        maxToRenderPerBatch={20}
        windowSize={10}
        removeClippedSubviews
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  emptyContent: {
    flexGrow: 1,
    justifyContent: 'center',
  },
});
