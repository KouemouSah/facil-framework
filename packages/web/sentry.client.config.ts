/**
 * Sentry — browser SDK init.
 *
 * Loaded automatically by @sentry/nextjs on every client-side mount of any
 * page. Captures uncaught exceptions, unhandled promise rejections, and
 * 5% sample of navigation transactions.
 *
 * Gating mirrors LogRocket: no-op in dev, no-op when DSN empty (forks).
 *
 * Sourcemaps: uploaded by `withSentryConfig` in next.config.mjs at build
 * time. Stack traces in Sentry Issues are unminified once the build that
 * produced the bundle has uploaded its sourcemaps.
 *
 * PII: send_default_pii=false. The wrapper additionally scrubs auth
 * routes via beforeSend.
 *
 * Bridge with LogRocket: every Sentry event gets `extra.logrocketURL`
 * attached so an Issue links straight to its replay
 * (see packages/web/src/core/observability/logrocket.ts:108).
 */
import * as Sentry from '@sentry/nextjs';

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN ?? '';
const IS_DEV = process.env.NODE_ENV === 'development';

if (DSN && !IS_DEV) {
  Sentry.init({
    dsn: DSN,
    environment: process.env.NEXT_PUBLIC_ENVIRONMENT ?? 'production',
    release: process.env.NEXT_PUBLIC_BUILD_VERSION ?? 'dev',

    // 5% sampling — calibrated for Sentry Free Developer plan
    // (5K errors + 10K transactions / month). Bump to 0.20 once on Team plan.
    tracesSampleRate: 0.05,
    // Replays are LogRocket's job; do not double-pay.
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,

    sendDefaultPii: false,

    beforeSend(event) {
      // Defense-in-depth: strip Authorization / Cookie if a future SDK
      // bump starts capturing them despite sendDefaultPii=false.
      if (event.request?.headers) {
        const h = event.request.headers as Record<string, string>;
        for (const k of Object.keys(h)) {
          if (['authorization', 'cookie', 'x-api-key'].includes(k.toLowerCase())) {
            h[k] = '[REDACTED]';
          }
        }
      }
      // Drop bodies on auth-issuing routes regardless of capture path.
      const url = event.request?.url ?? '';
      if (
        url.includes('/auth/login') ||
        url.includes('/auth/register') ||
        url.includes('/auth/2fa') ||
        url.includes('/auth/refresh')
      ) {
        if (event.request) event.request.data = undefined;
      }
      return event;
    },

    // Common React + framework noise — dropped at the SDK level so
    // the issues feed stays focused on real bugs.
    ignoreErrors: [
      // Browser extensions injecting scripts
      'top.GLOBALS',
      'ResizeObserver loop limit exceeded',
      'ResizeObserver loop completed with undelivered notifications',
      // Network noise we cannot act on
      'NetworkError when attempting to fetch resource',
      'Load failed',
    ],
  });

  Sentry.setTag('service', 'taxasge-web');
}
