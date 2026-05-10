/**
 * LogRocket SDK wrapper — single source of truth for init + identify +
 * capture. Every other module imports from here so we can tighten the
 * gating logic in one place.
 *
 * App ID: 0eqns2/facil  (set NEXT_PUBLIC_LOGROCKET_APP_ID at build time)
 *
 * Gating — init no-ops when ANY of:
 *   - NODE_ENV === 'development'  (dev hot-reload noise)
 *   - NEXT_PUBLIC_LOGROCKET_APP_ID empty  (contributor without secret)
 *   - typeof window === 'undefined'  (SSR safety)
 *
 * PII redaction layers:
 *   1. inputSanitizer: true → all <input> values masked
 *   2. requestSanitizer → strips Authorization / Cookie headers + login bodies
 *   3. responseSanitizer → strips token-issuing endpoint response bodies
 *   4. data-private DOM attribute → app team must opt-in NIF/email/phone fields
 *      (audit checklist: .claude/logrocket-setup.md §4)
 *
 * Identify policy: id + role + locale only. NEVER email, phone, NIF, address.
 */

import LogRocket from 'logrocket';
import setupLogRocketReact from 'logrocket-react';
import * as Sentry from '@sentry/nextjs';

const APP_ID = process.env.NEXT_PUBLIC_LOGROCKET_APP_ID ?? '';
const IS_DEV = process.env.NODE_ENV === 'development';
const IS_BROWSER = typeof window !== 'undefined';

let initialized = false;

export function isLogRocketActive(): boolean {
  return initialized && !!APP_ID && !IS_DEV && IS_BROWSER;
}

/**
 * Initialise LogRocket once. Idempotent — subsequent calls no-op.
 * Invoked from <LogRocketProvider> (client component mounted in <Providers>).
 */
export function initLogRocket(): void {
  if (initialized) return;
  initialized = true;

  if (!APP_ID || IS_DEV || !IS_BROWSER) return;

  LogRocket.init(APP_ID, {
    dom: {
      inputSanitizer: true,
      textSanitizer: false,
    },
    network: {
      requestSanitizer: (request) => {
        if (request.headers) {
          delete request.headers['Authorization'];
          delete request.headers['authorization'];
          delete request.headers['Cookie'];
          delete request.headers['cookie'];
        }
        if (
          request.url.includes('/auth/login') ||
          request.url.includes('/auth/register') ||
          request.url.includes('/auth/password-reset') ||
          request.url.includes('/auth/2fa')
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
    console: { isEnabled: { warn: true, error: true, log: false } },
    release: process.env.NEXT_PUBLIC_BUILD_VERSION ?? 'dev',
    shouldCaptureIP: false,
  });

  // logrocket-react v7 changed signature: setupReact() takes no args (it
  // imports the LogRocket singleton itself). v6 used to take (LogRocket).
  setupLogRocketReact();

  bridgeLogRocketToSentry();
}

/**
 * Bridge LogRocket session URL to Sentry — pushes the replay URL onto every
 * Sentry event so an Issue in Sentry links straight to its replay.
 *
 * Activated 2026-04-30 once @sentry/nextjs was wired (sentry.client/server/
 * edge.config.ts + withSentryConfig in next.config.mjs).
 *
 * Behaviour: getSessionURL fires once when LogRocket has a stable session
 * URL (after the first network flush, ~2-5 s). The URL is then attached
 * to the current Sentry scope's extras — every subsequent event captured
 * by Sentry on this tab inherits the link via `extra.logrocketURL`.
 */
export function bridgeLogRocketToSentry(): void {
  if (!isLogRocketActive()) return;
  LogRocket.getSessionURL((sessionURL) => {
    Sentry.getCurrentScope().setExtra('logrocketURL', sessionURL);
  });
}

/**
 * Attach the (non-PII) user context. Call after sign-in / refresh / profile update.
 * Pass null at sign-out to rotate to a fresh anonymous session.
 */
export function identifyLogRocket(
  user: { id: string; role?: string; locale?: string } | null,
): void {
  if (!isLogRocketActive()) return;
  if (!user) {
    LogRocket.startNewSession();
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
 * Auto-uncaught errors are picked up by LogRocket via window.onerror +
 * unhandledrejection — only call this when the error is suppressed.
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
