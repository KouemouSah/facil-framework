/**
 * Sentry — Next.js Edge runtime SDK init (middleware.ts + route handlers
 * with `export const runtime = 'edge'`).
 *
 * Edge runtime has a stripped-down API surface (no fs, no native crypto)
 * — Sentry SDK auto-detects and uses the edge-compatible variant.
 *
 * Same DSN as client + server; tag `runtime:edge` discriminates events.
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
  Sentry.setTag('runtime', 'edge');
}
