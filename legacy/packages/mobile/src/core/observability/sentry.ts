/**
 * Sentry React Native — initialisation + helpers.
 *
 * Design choices:
 *   - **No-op when DSN is absent.** Sentry init is gated behind
 *     `EXPO_PUBLIC_SENTRY_DSN`; if the env var is missing (e.g. local dev
 *     without an account) the SDK loads but every call becomes a cheap no-op.
 *   - **No PII.** A `beforeSend` hook strips the obvious PII patterns from
 *     event messages and contexts before they leave the device — defense in
 *     depth even if a console.error accidentally logs an email. We never set
 *     the user email or phone on the Sentry user context — only `id`,
 *     `role`, `locale`.
 *   - **Sample rates calibrated for the free Developer plan.** 5K errors +
 *     10K transactions / month / project. `tracesSampleRate: 0.05` (5%) keeps
 *     the transaction quota for ~10x the active user base before saturation.
 *   - **Disabled in `__DEV__`.** Errors during local development go to the
 *     RN red box; we don't pollute the Sentry inbox with dev noise.
 *
 * Usage:
 *   ```ts
 *   import { initSentry, captureException, setSentryUser } from '@core/observability/sentry';
 *   initSentry();                 // call once at boot
 *   setSentryUser({ id, role, locale });  // after login
 *   captureException(err, { tag, extra });
 *   ```
 */

import Constants from 'expo-constants';
import * as Sentry from '@sentry/react-native';

import { appConfig } from '@core/config/app';

const SENTRY_DSN = process.env.EXPO_PUBLIC_SENTRY_DSN ?? '';

let initialized = false;

/** True when Sentry is wired up and accepting events. False until `initSentry()` returns. */
export function isSentryActive(): boolean {
  return initialized && !!SENTRY_DSN && !__DEV__;
}

/**
 * Initialise Sentry once. Safe to call multiple times — subsequent calls are no-ops.
 *
 * Should be invoked from inside an `InteractionManager.runAfterInteractions`
 * (or similar deferred context) so the heavy init work doesn't compete with
 * the cold-start critical path. See `<DeferredEffects />` in `_layout.tsx`.
 */
export function initSentry(): void {
  if (initialized) return;
  initialized = true;

  if (!SENTRY_DSN) {
    // No DSN configured — leave the SDK as a no-op so the call sites stay simple.
    return;
  }
  if (__DEV__) {
    // Dev errors go to the RN red box — keep the Sentry inbox clean.
    return;
  }

  Sentry.init({
    dsn: SENTRY_DSN,
    // Phase 10/D — split development / preview / production / staging in the
    // Sentry dashboard. The EXPO_PUBLIC_ENV env var is set per build profile
    // in `packages/mobile/eas.json` (development = unset, preview = "preview",
    // production = "production"). Falling back to URL-based detection for
    // backwards compat with any pre-D11 build still in distribution.
    environment:
      process.env.EXPO_PUBLIC_ENV ??
      (process.env.EXPO_PUBLIC_API_URL?.includes('staging')
        ? 'staging'
        : 'production'),
    // Release identifier — falls back to expo-constants version if EAS doesn't pin it.
    release:
      Constants.expoConfig?.version ??
      Constants.manifest2?.extra?.expoGo?.version ??
      undefined,
    // Free Developer plan: 5K errors + 10K transactions / month. 5% transaction
    // sampling keeps headroom while still surfacing perf regressions.
    tracesSampleRate: 0.05,
    // Replay disabled — heavy on bandwidth and ToS-questionable for fiscal data.
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    // Enabled by default but explicit for the audit trail.
    enableAutoSessionTracking: true,
    // Strip every event of email/phone/NIF patterns before it leaves the
    // device — defense in depth.
    beforeSend(event) {
      try {
        return scrubPiiFromEvent(event);
      } catch {
        // Never crash the app over a redaction error — drop the event instead.
        return null;
      }
    },
    // Avoid sending PII attached by default integrations (IP address, cookies).
    sendDefaultPii: false,
  });
}

/**
 * Attach the (non-PII) user context. Call after login; pass `null` at logout.
 *
 * We store `id` / `role` / `locale` only — never email / phone / NIF.
 */
export function setSentryUser(
  user: { id: string; role?: string; locale?: string } | null,
): void {
  if (!isSentryActive()) return;
  if (!user) {
    Sentry.setUser(null);
    return;
  }
  Sentry.setUser({
    id: user.id,
    // No `email` / `username` / `ip_address` — Sentry's defaults would set them.
    role: user.role,
    locale: user.locale,
  });
}

/**
 * Capture an error with optional tags / extra.
 * No-op when Sentry is inactive.
 */
export function captureException(
  err: unknown,
  context?: { tag?: string; extra?: Record<string, unknown> },
): void {
  if (!isSentryActive()) return;
  Sentry.captureException(err, {
    tags: context?.tag ? { module: context.tag } : undefined,
    extra: context?.extra,
  });
}

/**
 * Capture a non-error event (e.g. unexpected state we want to investigate).
 */
export function captureMessage(
  msg: string,
  level: 'info' | 'warning' | 'error' = 'info',
  context?: { tag?: string; extra?: Record<string, unknown> },
): void {
  if (!isSentryActive()) return;
  Sentry.captureMessage(msg, {
    level,
    tags: context?.tag ? { module: context.tag } : undefined,
    extra: context?.extra,
  });
}

/**
 * Add a breadcrumb (auto-attached to the next captured event).
 */
export function addBreadcrumb(
  category: string,
  message: string,
  data?: Record<string, unknown>,
): void {
  if (!isSentryActive()) return;
  Sentry.addBreadcrumb({ category, message, data, level: 'info' });
}

/** React error boundary — wraps tree, captures + shows fallback. */
export const SentryErrorBoundary = Sentry.ErrorBoundary;

// ---------------------------------------------------------------------------
// PII scrubbing
// ---------------------------------------------------------------------------

const EMAIL_RE = /[\w.+-]+@[\w-]+\.[\w.-]+/g;
// Equatorial Guinea phone formats: +240222123456, 222123456, 555..., 333..., 551...
const PHONE_RE = /(?:\+?240\s*)?(?:222|555|551|333)\d{6}/g;
// NIF / tax IDs captured in two passes:
//   (a) labeled form: "NIF: 12345678X" / "TAX 9876XYZ" / "RUC ..." — easy.
//   (b) bare form: 8-12 char alphanumeric **with at least one letter AND one
//       digit** so internal hex UUIDs (no letters above F? false positive
//       there, accepted) and pure-digit IDs are NOT stripped by mistake.
const NIF_LABELED_RE = /\b(?:NIF|nif|TAX|tax|RUC|ruc)[\s:#-]*[A-Z0-9]{6,12}\b/g;
const NIF_BARE_RE =
  /\b(?=[A-Z0-9]{8,12}\b)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{8,12}\b/g;
// Generic identity document numbers — DNI / passport / driver licence labels
// that appear in audit logs around the workflows.
const DOC_RE = /\b(?:DNI|dni|PASS|pass|DUI|dui|CC|cc)[\s:#-]*[A-Z0-9]{6,15}\b/g;

function redact(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  return value
    .replace(EMAIL_RE, '[REDACTED-email]')
    .replace(PHONE_RE, '[REDACTED-phone]')
    .replace(NIF_LABELED_RE, '[REDACTED-nif]')
    .replace(NIF_BARE_RE, '[REDACTED-nif]')
    .replace(DOC_RE, '[REDACTED-doc]');
}

function scrubPiiFromEvent(event: Sentry.ErrorEvent): Sentry.ErrorEvent {
  if (event.message) event.message = redact(event.message) as string;
  // Exception messages
  for (const ex of event.exception?.values ?? []) {
    if (ex.value) ex.value = redact(ex.value) as string;
  }
  // Breadcrumb data
  for (const bc of event.breadcrumbs ?? []) {
    if (bc.message) bc.message = redact(bc.message) as string;
    if (bc.data) {
      for (const k of Object.keys(bc.data)) {
        bc.data[k] = redact(bc.data[k]);
      }
    }
  }
  // Extra
  if (event.extra) {
    for (const k of Object.keys(event.extra)) {
      event.extra[k] = redact(event.extra[k]);
    }
  }
  return event;
}

// Re-export the namespaced API for cases where callers need the full surface.
export { Sentry };

// Avoid an unused-import error when no other module references appConfig in this file.
void appConfig;
