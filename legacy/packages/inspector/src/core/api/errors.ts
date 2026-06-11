import { AxiosError } from 'axios';

export interface ApiError {
  message: string;
  status: number;
  detail?: string;
  validationErrors?: Array<{ field: string; message: string }>;
  code?: string;
  isNetworkError: boolean;
  isAuthError: boolean;
}

interface FastAPIValidationItem {
  loc: Array<string | number>;
  msg: string;
  type: string;
}

const DEFAULT_MESSAGES: Record<string, string> = {
  network: 'Error de conexion. Verifica tu conexion a internet.',
  timeout: 'La solicitud tardo demasiado. Intentalo de nuevo.',
  server: 'Error del servidor. Intentalo mas tarde.',
  unknown: 'Ha ocurrido un error inesperado.',
  unauthorized: 'Tu sesion ha expirado. Inicia sesion de nuevo.',
  forbidden: 'No tienes permiso para realizar esta accion.',
  notFound: 'El recurso solicitado no fue encontrado.',
  validation: 'Los datos enviados contienen errores.',
  rateLimit: 'Demasiadas solicitudes. Espera un momento.',
  conflict: 'Conflicto con el estado actual del recurso.',
} as const;

export function extractApiError(error: unknown): ApiError {
  if (isAxiosError(error) && error.response) {
    const { status, data } = error.response;
    const isAuth = status === 401;

    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as Record<string, unknown>).detail;

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
          status,
          detail: JSON.stringify(detail),
          validationErrors,
          isNetworkError: false,
          isAuthError: isAuth,
        };
      }

      if (typeof detail === 'string') {
        return {
          message: detail,
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

    const fallbackMessage = extractFallbackMessage(data) ?? getDefaultMessageForStatus(status);
    return {
      message: fallbackMessage,
      status,
      detail: typeof data === 'string' ? data : undefined,
      isNetworkError: false,
      isAuthError: isAuth,
    };
  }

  if (isAxiosError(error) && !error.response) {
    const isTimeout = error.code === 'ECONNABORTED' || error.code === 'ERR_CANCELED';
    return {
      message: isTimeout ? DEFAULT_MESSAGES.timeout : DEFAULT_MESSAGES.network,
      status: 0,
      detail: error.message,
      isNetworkError: true,
      isAuthError: false,
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message || DEFAULT_MESSAGES.unknown,
      status: 0,
      detail: error.message,
      isNetworkError: false,
      isAuthError: false,
    };
  }

  return {
    message: DEFAULT_MESSAGES.unknown,
    status: 0,
    detail: typeof error === 'string' ? error : undefined,
    isNetworkError: false,
    isAuthError: false,
  };
}

export function getErrorI18nKey(status: number): string {
  const statusKeyMap: Record<number, string> = {
    0: 'errors.network',
    400: 'errors.validation',
    401: 'errors.unauthorized',
    403: 'errors.forbidden',
    404: 'errors.notFound',
    409: 'errors.conflict',
    422: 'errors.validation',
    429: 'errors.rateLimit',
    500: 'errors.serverError',
    502: 'errors.serverError',
    503: 'errors.serverError',
    504: 'errors.serverError',
  };
  return statusKeyMap[status] ?? 'errors.serverError';
}

export function isHttpStatus(error: unknown, status: number): boolean {
  return isAxiosError(error) && error.response?.status === status;
}

export function isNetworkError(error: unknown): boolean {
  return isAxiosError(error) && !error.response;
}

/** P4: detect HTTP 403 PermissionError (fee_type / ministry scope check). */
export function isPermissionError(error: unknown): boolean {
  return isHttpStatus(error, 403);
}

/** P4: detect HTTP 429 Rate-limit responses. */
export function isRateLimitError(error: unknown): boolean {
  return isHttpStatus(error, 429);
}

/**
 * P4: extract Retry-After seconds from a 429 response.
 * Falls back to 60s if header is missing or unparseable.
 */
export function getRetryAfterSeconds(error: unknown): number {
  if (!isAxiosError(error) || !error.response) return 60;
  const raw = (error.response.headers as Record<string, unknown>)?.['retry-after'];
  if (typeof raw !== 'string' && typeof raw !== 'number') return 60;
  const parsed = parseInt(String(raw), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 60;
}

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
  if (typeof data === 'string' && data.length > 0 && data.length < 500) return data;
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
