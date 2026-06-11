/**
 * Notifications hook — listens for incoming pushes, persists them locally,
 * and exposes the inbox to UI consumers.
 *
 * Foreground push  → stored + invalidates queries listed in `data.invalidate_keys`.
 * Tap (any state)  → routed through deep-link router + marked as read.
 * Cold start tap   → handled in the root layout via getInitialNotificationResponse.
 */

import { useCallback, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { v4 as uuidv4 } from 'uuid';

import {
  type NotificationChannelId,
  type NotificationDataPayload,
  type StoredNotification,
  addNotification,
  deleteNotification,
  getNotifications,
  getUnreadCount,
  markAllAsRead as storageMarkAllAsRead,
  markAsRead as storageMarkAsRead,
  resolveRouteFromPayload,
  routeFromPayload,
  setupListeners,
} from '@core/notifications';

interface UseNotificationsResult {
  notifications: StoredNotification[];
  unreadCount: number;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  remove: (id: string) => void;
  refresh: () => void;
}

function buildStoredNotification(
  notif: { request: { content: { title?: string | null; body?: string | null; data?: unknown } } },
): StoredNotification {
  const data = (notif.request.content.data ?? {}) as NotificationDataPayload;
  const channel = (data.channel as NotificationChannelId | undefined) ?? 'default';
  const id = data.notif_id || uuidv4();
  const route = resolveRouteFromPayload(data);

  return {
    id,
    channelId: channel,
    title: notif.request.content.title ?? '',
    body: notif.request.content.body ?? '',
    data,
    receivedAt: Date.now(),
    readAt: null,
    deepLink: route,
  };
}

export function useNotifications(): UseNotificationsResult {
  const queryClient = useQueryClient();
  const [items, setItems] = useState<StoredNotification[]>(() => getNotifications());
  const [unread, setUnread] = useState<number>(() => getUnreadCount());

  const refresh = useCallback(() => {
    setItems(getNotifications());
    setUnread(getUnreadCount());
  }, []);

  useEffect(() => {
    const teardown = setupListeners(
      // onReceive (foreground or data-only background)
      (notification) => {
        const stored = buildStoredNotification(notification);
        addNotification(stored);
        // Invalidate React Query keys carried by the payload, comma-separated.
        if (stored.data.invalidate_keys) {
          stored.data.invalidate_keys.split(',').forEach((rawKey) => {
            const key = rawKey.trim();
            if (key) queryClient.invalidateQueries({ queryKey: [key] });
          });
        }
        refresh();
      },
      // onResponse (user tapped)
      (response) => {
        const data = response.notification.request.content.data as
          | NotificationDataPayload
          | undefined;
        const id = data?.notif_id;
        if (id) storageMarkAsRead(id);
        routeFromPayload(data);
        refresh();
      },
    );
    return teardown;
  }, [queryClient, refresh]);

  const markAsRead = useCallback(
    (id: string) => {
      storageMarkAsRead(id);
      refresh();
    },
    [refresh],
  );

  const markAllAsRead = useCallback(() => {
    storageMarkAllAsRead();
    refresh();
  }, [refresh]);

  const remove = useCallback(
    (id: string) => {
      deleteNotification(id);
      refresh();
    },
    [refresh],
  );

  return {
    notifications: items,
    unreadCount: unread,
    markAsRead,
    markAllAsRead,
    remove,
    refresh,
  };
}
