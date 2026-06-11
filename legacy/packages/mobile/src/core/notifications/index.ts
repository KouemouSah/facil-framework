/**
 * Public surface of the notifications core module.
 * Hooks live in `src/modules/notifications/hooks/` — they consume these helpers.
 */

export * from './types';
export {
  initNotifications,
  setupListeners,
  getInitialNotificationResponse,
} from './notifications-service';
export {
  requestPermission,
  getNativeDeviceToken,
  registerDeviceToken,
  clearStoredDeviceToken,
  subscribeToTokenRotation,
} from './device-token-service';
export {
  resolveRouteFromPayload,
  routeFromPayload,
} from './deep-link-router';
export {
  addNotification,
  getNotifications,
  getUnreadCount,
  markAsRead,
  markAllAsRead,
  deleteNotification,
  clearAll as clearAllNotifications,
} from './notifications-storage';
