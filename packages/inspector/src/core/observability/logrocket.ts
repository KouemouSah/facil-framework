/**
 * LogRocket React Native — initialisation + helpers (Inspector app).
 *
 * Inspector handles field-inspection workflows for agents (commerces,
 * licences, OMS, ayuntamiento). Replays are valuable for "agent reported
 * the form crashed mid-inspection" tickets that are otherwise impossible
 * to reproduce.
 *
 * Production-grade defaults (agents see citizen PII — NIF, addresses,
 * commercial licences):
 *   - **`textSanitizer: 'excluded'`** — every visible text is redacted by
 *     default. Use `<LRAllow>` to OPT IN safe content (button labels, nav,
 *     headers). Replays are less informative until the team audits and
 *     wraps non-PII zones; this trade-off is correct for fiscal data.
 *   - **`enableIPCapture: false`** — never geolocate users.
 *   - **`shouldDetectExceptions: true`** — auto-catch unhandled JS errors.
 *   - **`enablePersistence: true`** — buffer events on disk so a crash or
 *     poor-connectivity loss doesn't drop the recording.
 *   - **Network sanitiser** — Authorization + Cookie headers stripped;
 *     /auth/{login,register,password-reset,2fa} request bodies dropped;
 *     /auth/{login,refresh,2fa} response bodies dropped.
 *   - **Console capture: warn + error only.**
 *   - **Disabled in `__DEV__`.**
 *   - **Gated on `EXPO_PUBLIC_LOGROCKET_APP_ID`.**
 *
 * Identify policy: id + role + locale only. NEVER email / phone / NIF.
 *
 * Sentry bridge: Inspector does NOT yet ship Sentry RN. The bridge is a
 * documented no-op until `@sentry/react-native` is added to this package
 * — at which point the body becomes a 4-line edit (see comment below).
 *
 * Usage:
 *   ```ts
 *   import { initLogRocket, identifyLogRocket, captureLogRocketException }
 *     from '@core/observability/logrocket';
 *   initLogRocket();                                 // call once at boot
 *   identifyLogRocket({ id, role, locale });         // after login
 *   identifyLogRocket(null);                         // at logout
 *   captureLogRocketException(err, { extra });       // suppressed errors
 *   ```
 */

import LogRocket from '@logrocket/react-native';
import Constants from 'expo-constants';

const APP_ID = process.env.EXPO_PUBLIC_LOGROCKET_APP_ID ?? '';

let initialized = false;

/** True when LogRocket is wired up and accepting events. */
export function isLogRocketActive(): boolean {
  return initialized && !!APP_ID && !__DEV__;
}

/**
 * Initialise LogRocket once. Idempotent — subsequent calls no-op.
 *
 * Defer with `InteractionManager.runAfterInteractions` so SDK init doesn't
 * compete with the cold-start critical path.
 */
export function initLogRocket(): void {
  if (initialized) return;
  initialized = true;

  if (!APP_ID || __DEV__) return;

  const updateId =
    process.env.EXPO_PUBLIC_BUILD_VERSION ??
    Constants.expoConfig?.version ??
    null;

  LogRocket.init(APP_ID, {
    textSanitizer: 'excluded',
    enableIPCapture: false,
    enablePersistence: true,
    shouldDetectExceptions: true,
    updateId,
    network: {
      requestSanitizer: (request) => {
        if (request.headers) {
          delete request.headers['Authorization'];
          delete request.headers['authorization'];
          delete request.headers['Cookie'];
          delete request.headers['cookie'];
        }
        const url = request.url ?? '';
        if (
          url.includes('/auth/login') ||
          url.includes('/auth/register') ||
          url.includes('/auth/password-reset') ||
          url.includes('/auth/2fa')
        ) {
          request.body = undefined;
        }
        return request;
      },
      responseSanitizer: (response) => {
        const url = response.url ?? '';
        if (
          url.includes('/auth/login') ||
          url.includes('/auth/refresh') ||
          url.includes('/auth/2fa')
        ) {
          response.body = undefined;
        }
        return response;
      },
    },
    console: {
      isEnabled: { log: false, info: false, debug: false, warn: true, error: true },
    },
  });

  bridgeLogRocketToSentry();
}

/**
 * Bridge LogRocket session URL to Sentry. No-op until @sentry/react-native
 * is installed in this package. Replace body with:
 *
 *   import * as Sentry from '@sentry/react-native';
 *   LogRocket.getSessionURL((sessionURL) => {
 *     Sentry.getCurrentScope().setExtra('logrocketURL', sessionURL);
 *   });
 */
export function bridgeLogRocketToSentry(): void {
  // intentional no-op until Sentry RN is added to inspector
}

/**
 * Attach the (non-PII) user context. Call after login; pass `null` at logout.
 */
export function identifyLogRocket(
  user: { id: string; role?: string; locale?: string } | null,
): void {
  if (!isLogRocketActive()) return;
  if (!user) {
    void LogRocket.startNewSession();
    return;
  }
  LogRocket.identify(user.id, {
    role: user.role ?? 'unknown',
    locale: user.locale ?? 'es',
  });
}

/**
 * Track a discrete user-facing event (funnel-relevant moments only).
 */
export function trackLogRocket(
  event: string,
  props?: Record<string, string | number | boolean>,
): void {
  if (!isLogRocketActive()) return;
  LogRocket.track(event, props);
}

/**
 * Capture an exception explicitly. Auto-uncaught errors are picked up by
 * `shouldDetectExceptions: true` — only call this when the error is
 * suppressed by the caller.
 */
export function captureLogRocketException(
  err: unknown,
  extra?: Record<string, string | number | boolean>,
): void {
  if (!isLogRocketActive()) return;
  if (err instanceof Error) {
    LogRocket.captureException(err, extra ? { extra } : undefined);
  } else {
    LogRocket.captureMessage(typeof err === 'string' ? err : JSON.stringify(err), {
      extra,
    });
  }
}

export { LogRocket };
