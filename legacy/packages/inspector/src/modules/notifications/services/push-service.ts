/**
 * Push Notification Service — Register token, handle notifications
 *
 * Uses expo-notifications for token registration and notification handling.
 * FCM token is sent to backend on login and stored in users.recipient_device_token.
 */

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

import { apiPost } from '@core/api/client';

// Configure foreground notification behavior
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

/**
 * Register for push notifications and return the Expo push token.
 * Returns null if permissions denied or not a physical device.
 */
export async function registerForPushNotifications(): Promise<string | null> {
  // Push only works on physical devices (not emulator/simulator)
  if (!Constants.isDevice) {
    return null;
  }

  // Check existing permission
  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  // Request if not granted
  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    return null;
  }

  // Android notification channel
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Inspecciones',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#1565C0',
    });

    await Notifications.setNotificationChannelAsync('urgent', {
      name: 'Urgente',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 500, 250, 500],
      lightColor: '#C62828',
    });
  }

  try {
    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    const tokenData = await Notifications.getExpoPushTokenAsync({
      projectId: projectId ?? undefined,
    });
    return tokenData.data;
  } catch {
    return null;
  }
}

/**
 * Send push token to backend for storage.
 * Backend stores in users.recipient_device_token.
 */
export async function sendPushTokenToBackend(token: string): Promise<void> {
  try {
    const { API_ENDPOINTS } = await import('@core/api/endpoints');
    await apiPost(API_ENDPOINTS.users.deviceToken, {
      device_token: token,
      platform: Platform.OS,
      app: 'inspector',
    });
  } catch {
    // Non-blocking — token will be sent on next login
  }
}

/**
 * Parse notification data to extract deep link target.
 * Returns an Expo Router path or null.
 */
export function parseNotificationDeepLink(
  data: Record<string, unknown> | undefined,
): string | null {
  if (!data) return null;

  const type = data.type as string | undefined;
  const inspectionId = data.inspection_id as string | undefined;
  const missionId = data.mission_id as string | undefined;

  switch (type) {
    case 'SEAL_PROPOSED':
    case 'SEAL_APPROVED':
    case 'SEAL_REJECTED':
      return inspectionId ? `/inspection/${inspectionId}/seal-review` : null;

    case 'INSPECTION_COMPLETED':
    case 'MISE_EN_DEMEURE_ISSUED':
      return inspectionId ? `/inspection/${inspectionId}` : null;

    case 'MISSION_ASSIGNED':
    case 'MISSION_COMPLETED':
      return missionId ? `/supervisor/missions/${missionId}` : null;

    case 'RECONCILIATION_PENDING':
      return '/supervisor/reconciliation';

    default:
      return null;
  }
}
