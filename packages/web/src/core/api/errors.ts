/**
 * Shared API error handling utilities.
 * Extracts meaningful messages from FastAPI/Axios errors.
 *
 * @module core/api/errors
 */

import { isAxiosError } from 'axios';

/**
 * Well-known HTTP status codes mapped to i18n-friendly error keys.
 * These are used as fallbacks when the backend doesn't provide a `detail` string.
 * The keys match `common.errors.*` in the i18n files.
 */
const STATUS_ERROR_KEYS: Record<number, string> = {
  400: 'badRequest',
  401: 'unauthorized',
  403: 'forbidden',
  404: 'notFound',
  409: 'conflict',
  422: 'validationError',
  429: 'tooManyRequests',
  500: 'serverError',
  502: 'serverError',
  503: 'serviceUnavailable',
};

export interface ApiErrorInfo {
  /** Human-readable message (from backend detail or fallback) */
  message: string;
  /** HTTP status code, if available */
  status?: number;
  /** i18n key for status-based fallback (e.g. "forbidden") */
  statusKey?: string;
}

/**
 * Extract structured error info from an unknown error (typically AxiosError).
 *
 * Priority:
 *  1. FastAPI `detail` string → most specific
 *  2. Pydantic validation array → first error msg
 *  3. Status-code-based i18n key → contextual fallback
 *  4. Generic Error.message → last resort
 */
export function getApiErrorInfo(err: unknown): ApiErrorInfo {
  if (isAxiosError(err) && err.response) {
    const status = err.response.status;
    const data = err.response.data as Record<string, unknown> | undefined;
    const statusKey = STATUS_ERROR_KEYS[status];

    // FastAPI { detail: "Error message" }
    if (data && typeof data.detail === 'string') {
      return { message: data.detail, status, statusKey };
    }

    // Pydantic validation { detail: [{ msg: "..." }] }
    if (data && Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0] as Record<string, unknown>;
      if (typeof first.msg === 'string') {
        return { message: first.msg, status, statusKey };
      }
    }

    // FastAPI { detail: { message: "..." } }
    if (data && typeof data.detail === 'object' && data.detail !== null) {
      const detailObj = data.detail as Record<string, unknown>;
      if (typeof detailObj.message === 'string') {
        return { message: detailObj.message, status, statusKey };
      }
    }

    // No usable detail — return status key for i18n lookup
    return { message: err.message, status, statusKey };
  }

  if (err instanceof Error) {
    return { message: err.message };
  }

  return { message: String(err) };
}

// ═══════════════════════════════════════════════════════════════
// Structured API errors — used by bundle workflow, declarations,
// and any endpoint that returns `{detail: {code, message_es, fr, en}}`.
// ═══════════════════════════════════════════════════════════════

/**
 * Structured API error with a stable `code` and per-locale messages.
 * Any backend route may return this shape via HTTPException(detail={...}).
 */
export interface StructuredApiError {
  /** Stable metier code (e.g. PAYMENT_ALREADY_IN_PROGRESS) */
  code: string;
  /** Localized message for the current locale */
  message: string;
  /** HTTP status code, if available */
  status?: number;
  /** True when the request never reached the server (offline, CORS, timeout) */
  isNetworkError: boolean;
  /** True for 5xx server errors */
  isServerError: boolean;
  /** True when the client should offer a retry CTA */
  isRetryable: boolean;
  /** Raw backend detail object (for extracting extra fields like existing_request_id) */
  raw?: Record<string, unknown>;
}

type SupportedLocale = 'es' | 'fr' | 'en';

const RETRYABLE_STATUSES = new Set([408, 429, 502, 503, 504]);

/**
 * Extract a structured API error from an unknown caught error.
 *
 * Priority for the `code` field:
 *  1. `err.response.data.detail.code` (backend metier code)
 *  2. `err.response.data.detail` if it's a bare string → code = string itself
 *  3. Status-based fallback (HTTP_<status>)
 *  4. NETWORK_ERROR / UNKNOWN_ERROR
 *
 * Priority for the `message` field:
 *  1. `detail.message_<locale>` (exact locale)
 *  2. `detail.message_es` / `detail.message_en` (fallback chain)
 *  3. `detail.message` (legacy single-locale)
 *  4. `detail` string (flat FastAPI form)
 *  5. `err.message` (axios raw)
 */
export function extractApiError(
  err: unknown,
  locale: SupportedLocale = 'es',
): StructuredApiError {
  // Network-level (no response received)
  if (isAxiosError(err) && !err.response) {
    return {
      code: 'NETWORK_ERROR',
      message: err.message || 'Network error',
      isNetworkError: true,
      isServerError: false,
      isRetryable: true,
    };
  }

  if (isAxiosError(err) && err.response) {
    const status = err.response.status;
    const data = err.response.data as Record<string, unknown> | undefined;
    const detail = data?.detail;
    const isServerError = status >= 500;

    // Structured detail: { code, message_es, message_fr, message_en }
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const d = detail as Record<string, unknown>;
      const code =
        typeof d.code === 'string'
          ? d.code
          : `HTTP_${status}`;
      const message =
        pickLocalizedMessage(d, locale)
        ?? (typeof d.message === 'string' ? d.message : null)
        ?? err.message;

      return {
        code,
        message,
        status,
        isNetworkError: false,
        isServerError,
        isRetryable: isServerError || RETRYABLE_STATUSES.has(status),
        raw: d,
      };
    }

    // Flat string detail: "Some message"
    if (typeof detail === 'string') {
      return {
        code: `HTTP_${status}`,
        message: detail,
        status,
        isNetworkError: false,
        isServerError,
        isRetryable: isServerError || RETRYABLE_STATUSES.has(status),
      };
    }

    // Pydantic validation array: [{ msg: "..." }]
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as Record<string, unknown>;
      const msg = typeof first.msg === 'string' ? first.msg : err.message;
      return {
        code: 'VALIDATION_ERROR',
        message: msg,
        status,
        isNetworkError: false,
        isServerError: false,
        isRetryable: false,
      };
    }

    // No detail at all
    return {
      code: `HTTP_${status}`,
      message: err.message,
      status,
      isNetworkError: false,
      isServerError,
      isRetryable: isServerError || RETRYABLE_STATUSES.has(status),
    };
  }

  // Non-axios error (thrown by our own code)
  if (err instanceof Error) {
    return {
      code: 'UNKNOWN_ERROR',
      message: err.message,
      isNetworkError: false,
      isServerError: false,
      isRetryable: false,
    };
  }

  return {
    code: 'UNKNOWN_ERROR',
    message: String(err),
    isNetworkError: false,
    isServerError: false,
    isRetryable: false,
  };
}

function pickLocalizedMessage(
  detail: Record<string, unknown>,
  locale: SupportedLocale,
): string | null {
  const localized = detail[`message_${locale}`];
  if (typeof localized === 'string' && localized.length > 0) return localized;
  // Fallback chain: es → en → fr
  const fallbackOrder: SupportedLocale[] = ['es', 'en', 'fr'];
  for (const l of fallbackOrder) {
    const candidate = detail[`message_${l}`];
    if (typeof candidate === 'string' && candidate.length > 0) return candidate;
  }
  return null;
}

/**
 * Get a user-friendly error message string.
 *
 * @param err - The caught error (unknown)
 * @param fallback - Fallback message if nothing useful can be extracted
 * @param t - Optional i18n translator function for `common.errors.*` keys
 */
export function getApiErrorMessage(
  err: unknown,
  fallback: string,
  t?: (key: string) => string
): string {
  const info = getApiErrorInfo(err);

  // If we got a real detail message from the backend, use it
  if (isAxiosError(err) && err.response?.data) {
    const data = err.response.data as Record<string, unknown>;
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0] as Record<string, unknown>;
      if (typeof first.msg === 'string') return first.msg;
    }
  }

  // Try i18n status-based message
  if (t && info.statusKey) {
    try {
      const translated = t(`errors.${info.statusKey}`);
      // next-intl returns the key path if not found
      if (translated && !translated.includes('errors.')) return translated;
    } catch {
      // translator not available for this key
    }
  }

  // Fallback to generic Error.message (but NOT raw axios "Request failed with status code 409")
  if (info.message && !info.message.startsWith('Request failed with status code')) {
    return info.message;
  }

  return fallback;
}
