/**
 * Device token registration hook.
 *
 * Fires once auth is fully bootstrapped (`isAuthenticated && !isLoading`):
 *   1. Request push permission
 *   2. Fetch native FCM/APNs token
 *   3. Register with backend (idempotent — caches last token in MMKV)
 *   4. Subscribe to FCM/APNs token rotations and re-register
 *
 * Returns a status object the UI can use to surface a permission banner.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { useAuth } from '@core/hooks/use-auth';
import { logger } from '@core/logging/logger';
import {
  type DeviceTokenRegistrationStatus,
  type NativeDeviceToken,
  type NotificationPermissionStatus,
  getNativeDeviceToken,
  registerDeviceToken,
  requestPermission,
  subscribeToTokenRotation,
} from '@core/notifications';

interface UseDeviceTokenRegistrationResult {
  status: DeviceTokenRegistrationStatus;
  permission: NotificationPermissionStatus | null;
  /** Manually trigger the permission flow (e.g. from a banner CTA). */
  promptPermission: () => Promise<void>;
}

export function useDeviceTokenRegistration(): UseDeviceTokenRegistrationResult {
  const { isAuthenticated, isLoading } = useAuth();
  const [status, setStatus] = useState<DeviceTokenRegistrationStatus>('idle');
  const [permission, setPermission] = useState<NotificationPermissionStatus | null>(
    null,
  );
  const ranOnceRef = useRef(false);

  const runRegistration = useCallback(async () => {
    try {
      setStatus('requesting_permission');
      const perm = await requestPermission();
      setPermission(perm);
      if (perm !== 'granted') {
        setStatus('permission_denied');
        return;
      }

      setStatus('fetching_token');
      const token = await getNativeDeviceToken();
      if (!token) {
        setStatus('error');
        return;
      }

      setStatus('registering');
      await registerDeviceToken(token);
      setStatus('registered');
    } catch (err) {
      logger.error('notifications', err, 'registration failed');
      setStatus('error');
    }
  }, []);

  // Auto-run after auth bootstrap.
  useEffect(() => {
    if (isLoading || !isAuthenticated || ranOnceRef.current) return;
    ranOnceRef.current = true;
    void runRegistration();
  }, [isLoading, isAuthenticated, runRegistration]);

  // Re-register on FCM/APNs token rotation.
  useEffect(() => {
    if (!isAuthenticated) return;
    const unsubscribe = subscribeToTokenRotation(async (rotated: NativeDeviceToken) => {
      try {
        await registerDeviceToken(rotated);
      } catch (err) {
        logger.error('notifications', err, 'rotation re-register failed');
      }
    });
    return unsubscribe;
  }, [isAuthenticated]);

  const promptPermission = useCallback(async () => {
    ranOnceRef.current = true;
    await runRegistration();
  }, [runRegistration]);

  return { status, permission, promptPermission };
}
