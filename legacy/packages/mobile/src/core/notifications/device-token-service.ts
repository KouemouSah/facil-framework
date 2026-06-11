/**
 * Device token service — request permissions, fetch native FCM/APNs token,
 * and register it with the backend.
 *
 * Critical contract:
 *   - We use `getDevicePushTokenAsync()` (NOT `getExpoPushTokenAsync()`) so we
 *     receive the native FCM/APNs token directly. The backend talks to FCM/APNs
 *     via firebase-admin and does not understand ExpoPushTokens.
 *   - We pass `app: 'citizen'` explicitly. The backend defaults `app` to
 *     `'inspector'` (`DeviceTokenRequest.app: str = 'inspector'`), which would
 *     mis-categorize the user device.
 *   - Token registration is idempotent: we cache the last registered token in
 *     MMKV and skip the network call if unchanged. FCM token rotations are
 *     handled via `addPushTokenListener` upstream.
 */

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { apiPost } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import { getItem, setItem } from '@core/storage/mmkv';

import type {
  NativeDeviceToken,
  NotificationPermissionStatus,
} from './types';

const STORED_TOKEN_KEY = 'notifications.last_registered_token';

interface StoredTokenRecord {
  token: string;
  platform: 'android' | 'ios';
  registeredAt: number;
}

/**
 * Request push notification permissions.
 *
 * Android 13+ requires the runtime POST_NOTIFICATIONS permission; the SDK
 * handles the prompt. iOS prompts the user with a system dialog.
 */
export async function requestPermission(): Promise<NotificationPermissionStatus> {
  const existing = await Notifications.getPermissionsAsync();
  if (existing.status === 'granted') return 'granted';
  if (existing.status === 'denied' && !existing.canAskAgain) return 'denied';

  const result = await Notifications.requestPermissionsAsync({
    ios: {
      allowAlert: true,
      allowBadge: true,
      allowSound: true,
    },
  });

  if (result.status === 'granted') return 'granted';
  if (result.status === 'denied') return 'denied';
  return 'undetermined';
}

/**
 * Fetch the native device push token from the OS.
 * Returns null on web or when the platform doesn't support it.
 */
export async function getNativeDeviceToken(): Promise<NativeDeviceToken | null> {
  if (Platform.OS === 'web') return null;
  if (Platform.OS !== 'android' && Platform.OS !== 'ios') return null;

  const result = await Notifications.getDevicePushTokenAsync();
  if (!result?.data || typeof result.data !== 'string') return null;

  return {
    token: result.data,
    platform: Platform.OS,
  };
}

/**
 * Register the device token with the backend.
 * Idempotent — skips the POST if the token hasn't changed since last register.
 */
export async function registerDeviceToken(
  token: NativeDeviceToken,
): Promise<void> {
  const previous = getItem<StoredTokenRecord>(STORED_TOKEN_KEY);
  if (
    previous &&
    previous.token === token.token &&
    previous.platform === token.platform
  ) {
    return;
  }

  await apiPost(API_ENDPOINTS.users.deviceToken, {
    device_token: token.token,
    platform: token.platform,
    app: 'citizen',
  });

  setItem<StoredTokenRecord>(STORED_TOKEN_KEY, {
    token: token.token,
    platform: token.platform,
    registeredAt: Date.now(),
  });
}

/** Clear the cached token record — call on sign out. */
export function clearStoredDeviceToken(): void {
  setItem<StoredTokenRecord | null>(STORED_TOKEN_KEY, null);
}

/**
 * Subscribe to FCM/APNs token rotations. The OS may issue a new token at any
 * time; when that happens, re-register with the backend.
 */
export function subscribeToTokenRotation(
  onRotate: (token: NativeDeviceToken) => void,
): () => void {
  const subscription = Notifications.addPushTokenListener((event) => {
    if (!event?.data || typeof event.data !== 'string') return;
    if (Platform.OS !== 'android' && Platform.OS !== 'ios') return;
    onRotate({ token: event.data, platform: Platform.OS });
  });
  return () => subscription.remove();
}
