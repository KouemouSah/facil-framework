/**
 * Notifications service — boot-time setup for push notifications.
 *
 * Called once from the root layout. Responsibilities:
 *   - Configure how notifications appear in foreground (banner + sound + badge).
 *   - Create Android notification channels (importance, vibration, sound).
 *   - Expose helpers to subscribe to received / response events.
 *
 * iOS does not use channels — channel config is no-op on iOS by design of the SDK.
 *
 * NOTE: this file does NOT request permissions or fetch tokens — see
 * `device-token-service.ts` for that. Keep concerns separated so the boot path
 * can run without prompting the user for permissions on cold start.
 */

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import type { NotificationChannelId } from './types';

let initialized = false;

interface ChannelDefinition {
  id: NotificationChannelId;
  name: string;
  importance: Notifications.AndroidImportance;
  vibrationPattern?: number[];
}

const ANDROID_CHANNELS: ChannelDefinition[] = [
  {
    id: 'default',
    name: 'General',
    importance: Notifications.AndroidImportance.DEFAULT,
    vibrationPattern: [0, 250],
  },
  {
    id: 'payment',
    name: 'Pagos',
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
  },
  {
    id: 'agent_decision',
    name: 'Decisiones de agentes',
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
  },
  {
    id: 'appointment',
    name: 'Citas',
    importance: Notifications.AndroidImportance.DEFAULT,
    vibrationPattern: [0, 250],
  },
  {
    id: 'support',
    name: 'Soporte',
    importance: Notifications.AndroidImportance.DEFAULT,
    vibrationPattern: [0, 250],
  },
  {
    id: 'documents',
    name: 'Documentos',
    importance: Notifications.AndroidImportance.LOW,
  },
];

/**
 * Configure foreground display + Android channels. Idempotent.
 * Safe to call before auth bootstrap.
 */
export async function initNotifications(): Promise<void> {
  if (initialized) return;
  initialized = true;

  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: true,
    }),
  });

  if (Platform.OS === 'android') {
    await Promise.all(
      ANDROID_CHANNELS.map((channel) =>
        Notifications.setNotificationChannelAsync(channel.id, {
          name: channel.name,
          importance: channel.importance,
          vibrationPattern: channel.vibrationPattern,
          lightColor: '#1565C0',
        }),
      ),
    );
  }
}

/**
 * Subscribe to notifications. Returns a teardown function.
 *
 * - `onReceive` fires whenever a push arrives while the app is in foreground OR
 *   it's delivered in background (data-only payloads always trigger this on Android).
 * - `onResponse` fires when the user taps a notification (any state).
 */
export function setupListeners(
  onReceive: (notification: Notifications.Notification) => void,
  onResponse: (response: Notifications.NotificationResponse) => void,
): () => void {
  const receiveSub = Notifications.addNotificationReceivedListener(onReceive);
  const responseSub = Notifications.addNotificationResponseReceivedListener(onResponse);
  return () => {
    receiveSub.remove();
    responseSub.remove();
  };
}

/**
 * Get the response that opened the app, if launched via a notification tap.
 * Returns null if the app was launched normally.
 */
export async function getInitialNotificationResponse(): Promise<Notifications.NotificationResponse | null> {
  return Notifications.getLastNotificationResponseAsync();
}

/** Reset internal init flag — for tests. */
export function __resetForTests(): void {
  initialized = false;
}
