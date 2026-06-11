/**
 * Centralised logger for Facil mobile.
 *
 * - In `__DEV__`: routes to the matching `console.*` so the RN debugger keeps
 *   working as before.
 * - In production builds: `info` / `warn` are dropped to avoid leaking
 *   business logic via `READ_LOGS` (Android) and to keep the user's adb
 *   feed quiet. `error` is forwarded to Sentry as `captureException` (or
 *   `captureMessage` if no Error object). All severities can attach a
 *   breadcrumb in production for context on the next captured event.
 *
 * No third-party SDK is imported here directly — the call into Sentry is
 * routed through `@core/observability/sentry`, which is itself a no-op when
 * the DSN is absent. That means using the logger from places where the
 * runtime mode is unknown (tests, scripts, server-side modules) is safe.
 */

import {
  addBreadcrumb,
  captureException,
  captureMessage,
} from '@core/observability/sentry';

type Extra = Record<string, unknown> | undefined;

function tagPrefix(tag?: string): string {
  return tag ? `[${tag}]` : '';
}

export const logger = {
  /** Verbose / debug messages. Dev-only. */
  debug(tag: string, message: string, extra?: Extra): void {
    if (__DEV__) {
       
      console.debug(`${tagPrefix(tag)} ${message}`, extra ?? '');
    }
    // No prod breadcrumb — too noisy.
  },

  /** Informational message. Dev-console + production breadcrumb. */
  info(tag: string, message: string, extra?: Extra): void {
    if (__DEV__) {
       
      console.log(`${tagPrefix(tag)} ${message}`, extra ?? '');
      return;
    }
    addBreadcrumb(tag, message, extra);
  },

  /** Warning — non-fatal anomaly. Dev-console + production breadcrumb. */
  warn(tag: string, message: string, extra?: Extra): void {
    if (__DEV__) {
       
      console.warn(`${tagPrefix(tag)} ${message}`, extra ?? '');
      return;
    }
    addBreadcrumb(tag, `WARN: ${message}`, extra);
  },

  /**
   * Error — caught exception or unexpected state.
   * Dev: console.error.
   * Prod: forwarded to Sentry. The first argument is the cause (Error or
   * unknown). The second is a free-text description; the third bag of extras.
   */
  error(tag: string, cause: unknown, message?: string, extra?: Extra): void {
    if (__DEV__) {
       
      console.error(`${tagPrefix(tag)} ${message ?? ''}`, cause, extra ?? '');
      return;
    }
    if (cause instanceof Error) {
      captureException(cause, {
        tag,
        extra: { description: message, ...(extra ?? {}) },
      });
    } else {
      captureMessage(message ?? String(cause), 'error', {
        tag,
        extra: { cause: String(cause), ...(extra ?? {}) },
      });
    }
  },
};
