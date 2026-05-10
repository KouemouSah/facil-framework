/**
 * Notification badge hook — exposes the unread count for the tab bar.
 *
 * Reads MMKV directly (sync). The count is refreshed by `useNotifications`
 * via the shared queryClient cache, so this hook is only a thin reader.
 */

import { useEffect, useState } from 'react';

import { getUnreadCount } from '@core/notifications';

export function useNotificationBadge(): number {
  const [count, setCount] = useState<number>(() => getUnreadCount());

  useEffect(() => {
    // Poll every 5s as a safety net; the in-app emitter is fed by
    // useNotifications when running, but the tab bar may render before that.
    const id = setInterval(() => {
      const next = getUnreadCount();
      setCount((current) => (current === next ? current : next));
    }, 5000);
    return () => clearInterval(id);
  }, []);

  return count;
}
