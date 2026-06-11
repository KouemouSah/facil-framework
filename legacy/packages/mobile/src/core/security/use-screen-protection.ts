/**
 * useScreenProtection — Prevents screenshots on sensitive screens
 *
 * Uses FLAG_SECURE on Android (prevents screenshots + screen recording).
 * Call in any screen component that shows sensitive data.
 *
 * Automatically activates on mount and deactivates on unmount,
 * so non-sensitive screens remain capturable.
 */

import { useEffect } from 'react';
import * as ScreenCapture from 'expo-screen-capture';

/**
 * Prevents screenshots while the calling component is mounted.
 * No-op if the module is unavailable.
 */
export function useScreenProtection() {
  useEffect(() => {
    ScreenCapture.preventScreenCaptureAsync().catch(() => {});
    return () => {
      ScreenCapture.allowScreenCaptureAsync().catch(() => {});
    };
  }, []);
}
