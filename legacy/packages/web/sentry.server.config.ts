/**
 * Sentry — Next.js server-side SDK init (Node runtime: SSR, RSC, route
 * handlers, server actions).
 *
 * Note: NEXT_PUBLIC_SENTRY_DSN is intentionally reused — the same project
 * receives client + server events for one Next.js app. Filter by tag
 * `runtime:node` vs `runtime:browser` in the Sentry UI to disambiguate.
 *
 * Sampling 5% mirrors the client config to stay within the Free plan
 * envelope. Server-side errors are usually rarer but they're correlated
 * to client errors via the same `release` tag.
 */
import * as Sentry from '@sentry/nextjs';

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN ?? process.env.SENTRY_DSN ?? '';
const IS_DEV = process.env.NODE_ENV === 'development';

if (DSN && !IS_DEV) {
  Sentry.init({
    dsn: DSN,
    environment: process.env.NEXT_PUBLIC_ENVIRONMENT ?? 'production',
    release: process.env.NEXT_PUBLIC_BUILD_VERSION ?? 'dev',
    tracesSampleRate: 0.05,
    sendDefaultPii: false,
  });

  Sentry.setTag('service', 'taxasge-web');
  Sentry.setTag('runtime', 'node');
}
