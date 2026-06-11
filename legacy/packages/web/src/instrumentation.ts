/**
 * Next.js instrumentation entry point.
 *
 * Loaded once per Next.js process at startup (Node + Edge runtimes).
 * Required by @sentry/nextjs v8+ — replaces the old Sentry-injected hook
 * model. Without this file, sentry.server.config.ts and
 * sentry.edge.config.ts are NEVER loaded for SSR / route handlers.
 *
 * The browser variant is loaded by @sentry/nextjs's webpack plugin
 * directly from `sentry.client.config.ts` at the project root — no
 * import needed here.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    await import('../sentry.server.config');
  }
  if (process.env.NEXT_RUNTIME === 'edge') {
    await import('../sentry.edge.config');
  }
}
