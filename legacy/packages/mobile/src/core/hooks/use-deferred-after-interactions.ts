/**
 * useDeferredAfterInteractions — gate non-critical work behind the first
 * paint.
 *
 * React Native's InteractionManager fires its callback after the JS thread
 * has nothing pressing to do — typically right after the first frame is
 * rendered and any in-flight transitions / animations have settled.
 *
 * Use this hook to delay things that are *useful* but not *required* for
 * the initial render: push-notification setup, device-token registration,
 * Sentry init, analytics flush, prefetches. The user sees the splash → the
 * first screen → and only then we fire the heavy work.
 *
 * Returns:
 *   - `ready: false` until interactions settle (≈ first paint + transitions)
 *   - `ready: true` from the next render onward, for the rest of the lifetime
 *     of the component.
 *
 * Safe to call inside `useEffect` chains because it only flips state once.
 */

import { useEffect, useState } from 'react';
import { InteractionManager } from 'react-native';

export function useDeferredAfterInteractions(): boolean {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // `runAfterInteractions` returns a handle whose `.cancel()` we should
    // call if we tear down before it fires (avoids setState on unmounted).
    const handle = InteractionManager.runAfterInteractions(() => {
      setReady(true);
    });
    return () => handle.cancel();
  }, []);

  return ready;
}
