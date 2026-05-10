/**
 * useScreenProtection - Prevents screenshots in production builds
 *
 * Uses expo-screen-capture to set FLAG_SECURE on Android,
 * preventing screenshots and screen recording of sensitive inspection data.
 *
 * - Active only in production (__DEV__ === false)
 * - Activates on mount, deactivates on unmount
 * - No-op if the module is unavailable or in dev mode
 */

import { useEffect } from 'react';
import * as ScreenCapture from 'expo-screen-capture';

export function useScreenProtection() {
  useEffect(() => {
    if (__DEV__) return;

    ScreenCapture.preventScreenCaptureAsync().catch(() => {});
    return () => {
      ScreenCapture.allowScreenCaptureAsync().catch(() => {});
    };
  }, []);
}
