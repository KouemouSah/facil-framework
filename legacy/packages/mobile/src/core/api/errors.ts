/**
 * API Error Extraction Utilities
 *
 * Handles FastAPI error response formats:
 * - Simple: { detail: "string" }
 * - Validation: { detail: [{ loc: [...], msg: "string", type: "string" }] }
 * - Generic HTTP errors
 *
 * Designed for Facil mobile app (React Native / Expo SDK 54).
 */

import { AxiosError } from 'axios';

/** Structured API error for consistent error handling across the app. */
export interface ApiError {
  /** Human-readable error message (may be localized by backend). */
  message: string;
  /** i18n key for displaying translated error to user (e.g. 'errors.network'). */
  i18nKey: string;
  /** HTTP status code (0 if no response received, e.g. network error). */
  status: number;
  /** Raw detail string from FastAPI response, if available. */
  detail?: string;
  /** Pydantic validation errors mapped to field + message pairs. */
  validationErrors?: { field: string; message: string }[];
  /** Original error code from backend, if provided. */
  code?: string;
  /** Whether this is a network/connectivity error (no server response). */
  isNetworkError: boolean;
  /** Whether the token has expired and refresh failed (user must re-login). */
  isAuthError: boolean;
}

/**
 * FastAPI validation error item shape.
 * @see https://fastapi.tiangolo.com/tutorial/handling-errors/
 */
interface FastAPIValidationItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** Default fallback messages by category (Spanish - Facil primary language). */
const DEFAULT_MESSAGES: Record<string, string> = {
  network: 'Error de conexión. Verifica tu conexión a internet.',
  timeout: 'La solicitud tardó demasiado. Inténtalo de nuevo.',
  server: 'Error del servidor. Inténtalo más tarde.',
  unknown: 'Ha ocurrido un error inesperado.',
  unauthorized: 'Tu sesión ha expirado. Inicia sesión de nuevo.',
  forbidden: 'No tienes permiso para realizar esta acción.',
  notFound: 'El recurso solicitado no fue encontrado.',
  validation: 'Los datos enviados contienen errores.',
  rateLimit: 'Demasiadas solicitudes. Espera un momento.',
  conflict: 'Conflicto con el estado actual del recurso.',
} as const;

/**
 * Extract a structured ApiError from any caught error.
 *
 * Handles:
 * 1. AxiosError with FastAPI JSON response (detail string or validation array)
 * 2. AxiosError with no response (network error / timeout)
 * 3. Generic Error instances
 * 4. Unknown thrown values
 */
export function extractApiError(error: unknown): ApiError {
  // Case 1: Axios error with response from the server
  if (isAxiosError(error) && error.response) {
    const { status, data } = error.response;
    const isAuth = status === 401;

    // FastAPI validation errors: { detail: [{ loc, msg, type }] }
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as Record<string, unknown>).detail;

      // Array of validation errors (Pydantic)
      if (Array.isArray(detail)) {
        const validationErrors = detail
          .filter(isValidationItem)
          .map((item) => ({
            field: item.loc.slice(1).join('.') || item.loc[0]?.toString() || 'unknown',
            message: item.msg,
          }));

        return {
          message: validationErrors.length > 0
            ? validationErrors.map((e) => `${e.field}: ${e.message}`).join('; ')
            : DEFAULT_MESSAGES.validation,
          i18nKey: 'errors.validation',
          status,
          detail: JSON.stringify(detail),
          validationErrors,
          isNetworkError: false,
          isAuthError: isAuth,
        };
      }

      // Simple string detail
      if (typeof detail === 'string') {
        return {
          message: detail,
          i18nKey: getErrorI18nKey(status),
          status,
          detail,
          code: typeof (data as Record<string, unknown>).code === 'string'
            ? (data as Record<string, unknown>).code as string
            : undefined,
          isNetworkError: false,
          isAuthError: isAuth,
        };
      }
    }

    // Non-standard response body: try to extract a message
    const fallbackMessage = extractFallbackMessage(data) ?? getDefaultMessageForStatus(status);
    return {
      message: fallbackMessage,
      i18nKey: getErrorI18nKey(status),
      status,
      detail: typeof data === 'string' ? data : undefined,
      isNetworkError: false,
      isAuthError: isAuth,
    };
  }

  // Case 2: Axios error with no response (network / timeout / abort)
  if (isAxiosError(error) && !error.response) {
    const isTimeout = error.code === 'ECONNABORTED' || error.code === 'ERR_CANCELED';
    return {
      message: isTimeout ? DEFAULT_MESSAGES.timeout : DEFAULT_MESSAGES.network,
      i18nKey: isTimeout ? 'errors.timeout' : 'errors.network',
      status: 0,
      detail: error.message,
      isNetworkError: true,
      isAuthError: false,
    };
  }

  // Case 3: Standard Error
  if (error instanceof Error) {
    return {
      message: error.message || DEFAULT_MESSAGES.unknown,
      i18nKey: 'errors.unknown',
      status: 0,
      detail: error.message,
      isNetworkError: false,
      isAuthError: false,
    };
  }

  // Case 4: Unknown thrown value
  return {
    message: DEFAULT_MESSAGES.unknown,
    i18nKey: 'errors.unknown',
    status: 0,
    detail: typeof error === 'string' ? error : undefined,
    isNetworkError: false,
    isAuthError: false,
  };
}

/**
 * Map HTTP status code to an i18n translation key.
 * Keys match the flat structure in locale files: `errors.<key>`
 */
export function getErrorI18nKey(status: number): string {
  const statusKeyMap: Record<number, string> = {
    0: 'errors.network',
    400: 'errors.validation',
    401: 'errors.unauthorized',
    403: 'errors.forbidden',
    404: 'errors.notFound',
    409: 'errors.serverError',
    422: 'errors.validation',
    429: 'errors.rateLimit',
    500: 'errors.serverError',
    502: 'errors.serverError',
    503: 'errors.serverError',
    504: 'errors.serverError',
  };

  return statusKeyMap[status] ?? 'errors.serverError';
}

/**
 * Check if a given error is a specific HTTP status.
 * Useful for conditional handling in catch blocks.
 */
export function isHttpStatus(error: unknown, status: number): boolean {
  return isAxiosError(error) && error.response?.status === status;
}

/**
 * Check if the error represents a network connectivity issue
 * (no response from server at all).
 */
export function isNetworkError(error: unknown): boolean {
  return isAxiosError(error) && !error.response;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function isAxiosError(error: unknown): error is AxiosError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'isAxiosError' in error &&
    (error as AxiosError).isAxiosError === true
  );
}

function isValidationItem(item: unknown): item is FastAPIValidationItem {
  return (
    typeof item === 'object' &&
    item !== null &&
    'loc' in item &&
    'msg' in item &&
    Array.isArray((item as FastAPIValidationItem).loc) &&
    typeof (item as FastAPIValidationItem).msg === 'string'
  );
}

function extractFallbackMessage(data: unknown): string | null {
  if (typeof data === 'string' && data.length > 0 && data.length < 500) {
    return data;
  }
  if (typeof data === 'object' && data !== null) {
    const obj = data as Record<string, unknown>;
    if (typeof obj.message === 'string') return obj.message;
    if (typeof obj.error === 'string') return obj.error;
  }
  return null;
}

function getDefaultMessageForStatus(status: number): string {
  if (status === 401) return DEFAULT_MESSAGES.unauthorized;
  if (status === 403) return DEFAULT_MESSAGES.forbidden;
  if (status === 404) return DEFAULT_MESSAGES.notFound;
  if (status === 409) return DEFAULT_MESSAGES.conflict;
  if (status === 422) return DEFAULT_MESSAGES.validation;
  if (status === 429) return DEFAULT_MESSAGES.rateLimit;
  if (status >= 500) return DEFAULT_MESSAGES.server;
  return DEFAULT_MESSAGES.unknown;
}
