/**
 * Server-side notifications sync.
 *
 * Pulls the audit-trail notifications from
 *   GET /service-requests/notifications
 * and merges them into the local MMKV inbox. Each backend item is mapped to a
 * `StoredNotification` (channel `default`, deepLink `/(tabs)/requests/{id}`)
 * and inserted via `addNotification`, which dedupes by id — so re-running the
 * sync is idempotent.
 *
 * Why both server and MMKV?
 *   - Server is authoritative: it never loses an entry, but only carries
 *     audit-trail-style notifications that are also a real `service_request_history`
 *     row. Push-only payloads (e.g. permission requests, device-token alerts)
 *     never go through history and therefore only live in MMKV.
 *   - MMKV is the always-loaded inbox, fast, offline-tolerant, and the single
 *     source of truth for the unread badge.
 */

import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import {
  type StoredNotification,
  addNotification,
  getNotifications,
  resolveRouteFromPayload,
} from '@core/notifications';

import {
  listCitizenNotifications,
  type ServerCitizenNotification,
} from '../services/citizen-notifications-api';

interface UseServerNotificationsSyncResult {
  /** Imported = pulled from server AND not previously in MMKV. */
  isSyncing: boolean;
  lastError: Error | null;
  importedCount: number;
  /** Triggers a sync. Safe to call repeatedly — dedup via `addNotification`. */
  sync: () => Promise<void>;
}

function toStored(item: ServerCitizenNotification): StoredNotification {
  const data = {
    notif_id: item.id,
    channel: 'default' as const,
    request_id: item.request_id,
    deep_link: `/(tabs)/requests/${item.request_id}`,
    action: item.action,
    performer_role: item.performer_role,
  };
  return {
    id: item.id,
    channelId: 'default',
    title: item.title,
    body: item.message ?? '',
    data,
    receivedAt: new Date(item.performed_at).getTime(),
    readAt: item.is_new ? null : Date.now(),
    deepLink: resolveRouteFromPayload(data),
  };
}

export function useServerNotificationsSync(): UseServerNotificationsSyncResult {
  const queryClient = useQueryClient();
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastError, setLastError] = useState<Error | null>(null);
  const [importedCount, setImportedCount] = useState(0);

  const sync = useCallback(async () => {
    setIsSyncing(true);
    setLastError(null);
    try {
      const res = await listCitizenNotifications({ page: 1, page_size: 50 });
      const existingIds = new Set(getNotifications().map((n) => n.id));
      let imported = 0;
      for (const item of res.items) {
        if (existingIds.has(item.id)) continue;
        addNotification(toStored(item));
        imported += 1;
      }
      setImportedCount(imported);
      // Notify any list consumers that the inbox refreshed.
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    } catch (err) {
      setLastError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSyncing(false);
    }
  }, [queryClient]);

  return { isSyncing, lastError, importedCount, sync };
}
