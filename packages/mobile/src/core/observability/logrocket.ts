/**
 * LogRocket React Native — initialisation + helpers.
 *
 * Companion to `sentry.ts`:
 *   - Sentry RN  → crash reports + native stack traces + alerting (low quota)
 *   - LogRocket  → session replay (touches, screens, redux state, network) +
 *                  console + perf. Useful for "what did the user do before
 *                  the bug" investigations Sentry alone can't answer.
 *
 * Production-grade defaults (this is a fiscal app — NIF, passport, declarations):
 *   - **`textSanitizer: 'excluded'`** — every visible text is redacted by
 *     default. Use `<LRAllow>` to OPT IN safe content (button labels, nav,
 *     headers). This is the opposite of the web SDK (where you opt OUT
 *     via `data-private`). Privacy-first; replays are less informative
 *     until the team audits and wraps non-PII zones.
 *   - **`enableIPCapture: false`** — never geolocate users. Mirrors
 *     `sendDefaultPii: false` on the Sentry side.
 *   - **`shouldDetectExceptions: true`** — auto-catch Raven.js exceptions
 *     so unhandled errors land in LogRocket without manual wiring.
 *   - **`enablePersistence: true`** — buffer events on disk so a crash or
 *     poor-connectivity loss doesn't drop the recording.
 *   - **Network sanitiser** — Authorization + Cookie headers stripped;
 *     /auth/{login,register,password-reset,2fa} request bodies dropped;
 *     /auth/{login,refresh,2fa} response bodies dropped (no JWT or
 *     plaintext password leaving the device, ever).
 *   - **Console capture: warn + error only.** Drop log/info/debug — too
 *     noisy at scale and may carry developer context.
 *   - **Disabled in `__DEV__`** — hot-reload + Metro errors would saturate
 *     the inbox. Local debugging stays in the RN red box.
 *   - **Gated on `EXPO_PUBLIC_LOGROCKET_APP_ID`** — missing env var → SDK
 *     no-ops. Contributor checkouts stay clean.
 *
 * Identify policy: id + role + locale only. NEVER email / phone / NIF.
 *
 * Sentry bridge: when both SDKs are active, the LogRocket session URL is
 * pinned onto every Sentry event as `extra.logrocketURL`, so a Sentry
 * issue deep-links to its replay in one click.
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
import * as Sentry from '@sentry/react-native';
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
 * Call from inside `InteractionManager.runAfterInteractions` (deferred
 * effects) so SDK init doesn't compete with the cold-start critical path.
 * See `<DeferredEffects />` in `_layout.tsx`.
 */
export function initLogRocket(): void {
  if (initialized) return;
  initialized = true;

  if (!APP_ID || __DEV__) return;

  // Build version stamp — surfaced to LogRocket as updateId so we can split
  // sessions per build in the dashboard. Falls back to expo-constants version.
  const updateId =
    process.env.EXPO_PUBLIC_BUILD_VERSION ??
    Constants.expoConfig?.version ??
    null;

  LogRocket.init(APP_ID, {
    // ── Privacy-first text capture ────────────────────────────────────
    // Every text node is redacted by default. Opt-in via <LRAllow> in the
    // app for non-PII content (button labels, navigation, public info).
    textSanitizer: 'excluded',
    enableIPCapture: false,

    // ── Resilience ───────────────────────────────────────────────────
    enablePersistence: true,
    shouldDetectExceptions: true,

    // ── Build identification ─────────────────────────────────────────
    updateId,

    // ── Network capture ──────────────────────────────────────────────
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

    // ── Console capture ──────────────────────────────────────────────
    console: {
      isEnabled: { log: false, info: false, debug: false, warn: true, error: true },
    },
  });

  bridgeLogRocketToSentry();
}

/**
 * Pin the LogRocket session URL onto every Sentry event. No-op if Sentry
 * isn't initialised on this device. Safe to call multiple times.
 */
export function bridgeLogRocketToSentry(): void {
  if (!isLogRocketActive()) return;
  try {
    LogRocket.getSessionURL((sessionURL: string) => {
      Sentry.getCurrentScope().setExtra('logrocketURL', sessionURL);
    });
  } catch {
    // Sentry not initialised → silently skip.
  }
}

/**
 * Attach the (non-PII) user context. Call after login; pass `null` at logout
 * to rotate to a fresh anonymous session.
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
 * Track a discrete user-facing event (funnel-relevant moments only — every
 * call costs LogRocket quota; do NOT track per-button-click).
 */
export function trackLogRocket(
  event: string,
  props?: Record<string, string | number | boolean>,
): void {
  if (!isLogRocketActive()) return;
  LogRocket.track(event, props);
}

/**
 * Capture an exception explicitly (try/catch swallow path or ErrorBoundary).
 * Auto-uncaught errors are picked up by `shouldDetectExceptions: true` —
 * only call this when the error is suppressed by the caller.
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
