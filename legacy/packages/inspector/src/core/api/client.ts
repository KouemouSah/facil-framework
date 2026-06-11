/**
 * Axios API Client for Facil Inspeccion App
 *
 * Configured for the Facil backend (FastAPI on Cloud Run) with:
 * - Automatic Bearer token injection from secure storage
 * - Accept-Language header from app locale
 * - Token refresh with request queuing (max 50, 10s timeout)
 * - Adaptive timeout (30s default, configurable)
 * - FastAPI error format extraction
 */

import axios, {
  AxiosError,
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';

import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
} from '@core/auth/auth-storage';
import { appConfig } from '@core/config/app';
import { API_ENDPOINTS } from '@core/api/endpoints';

const MAX_QUEUE_SIZE = 50;
const REFRESH_TIMEOUT_MS = 10_000;

// OWASP M5: Enforce HTTPS — reject HTTP in production
const baseUrl = appConfig.api.baseUrl;
if (!__DEV__ && !baseUrl.startsWith('https://')) {
  throw new Error('SECURITY: API base URL must use HTTPS in production');
}

const apiClient: AxiosInstance = axios.create({
  baseURL: `${baseUrl}/api/${appConfig.api.version}`,
  headers: {
    'Content-Type': 'application/json',
    'X-App-Version': appConfig.app.version,
    'X-App-Platform': 'inspector-android',
  },
  timeout: appConfig.api.timeout,
  withCredentials: false,
  maxContentLength: 10 * 1024 * 1024, // 10MB max response
  maxBodyLength: 10 * 1024 * 1024,    // 10MB max request
});

let currentLocale: string = 'es';

apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const accessToken = await getAccessToken();
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    if (config.headers) {
      config.headers['Accept-Language'] = currentLocale;
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error),
);

export function setApiLocale(locale: string): void {
  if (['es', 'fr', 'en'].includes(locale)) {
    currentLocale = locale;
  }
}

export function getApiLocale(): string {
  return currentLocale;
}

interface QueueItem {
  resolve: (value: string | null) => void;
  reject: (reason: Error) => void;
}

let isRefreshing = false;
let failedQueue: QueueItem[] = [];

function processQueue(error: Error | null, token: string | null = null): void {
  const queue = failedQueue;
  failedQueue = [];
  queue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token);
  });
}

/**
 * P4: Automatic retry for transient network errors on safe requests.
 * Only retries if:
 *   - No response (network/timeout) OR 5xx OR 429
 *   - Method is GET, OR request has Idempotency-Key header (safe to replay)
 *   - Retry count not exceeded (_retryCount < MAX_NETWORK_RETRIES)
 * Uses exponential backoff (500ms, 1500ms).
 */
const MAX_NETWORK_RETRIES = 2;

async function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryableError(error: AxiosError): boolean {
  if (!error.config) return false;
  // Network errors (no response)
  if (!error.response) return true;
  const status = error.response.status;
  // 5xx server errors are safe to retry
  if (status >= 500 && status < 600) return true;
  // 429 rate limit — caller should observe Retry-After; skip auto-retry here
  return false;
}

function isIdempotentRequest(config: InternalAxiosRequestConfig): boolean {
  const method = (config.method ?? 'get').toUpperCase();
  if (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') return true;
  // For mutations, only retry if the caller opted in with an Idempotency-Key
  const headers = (config.headers ?? {}) as Record<string, unknown>;
  return Boolean(headers['Idempotency-Key'] || headers['idempotency-key']);
}

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & {
      _retry?: boolean;
      _retryCount?: number;
    }) | undefined;

    // Auto-retry transient errors for idempotent / idempotency-keyed requests
    if (
      originalRequest
      && isRetryableError(error)
      && isIdempotentRequest(originalRequest)
    ) {
      const count = originalRequest._retryCount ?? 0;
      if (count < MAX_NETWORK_RETRIES) {
        originalRequest._retryCount = count + 1;
        const delay = 500 * Math.pow(3, count); // 500ms, 1500ms
        await wait(delay);
        return apiClient(originalRequest);
      }
    }

    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      if (failedQueue.length >= MAX_QUEUE_SIZE) {
        return Promise.reject(new Error('Too many pending requests during token refresh'));
      }
      return new Promise<string | null>((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then((newToken) => {
        if (newToken && originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) {
        await clearTokens();
        processQueue(new Error('No refresh token available'));
        isRefreshing = false;
        return Promise.reject(error);
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS);

      const refreshResponse = await axios.post<{
        access_token: string;
        refresh_token: string;
      }>(
        `${appConfig.api.baseUrl}/api/${appConfig.api.version}${API_ENDPOINTS.auth.refresh}`,
        { refresh_token: refreshToken },
        {
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          timeout: REFRESH_TIMEOUT_MS,
        },
      );

      clearTimeout(timeoutId);
      const { access_token, refresh_token: newRefreshToken } = refreshResponse.data;
      await setTokens(access_token, newRefreshToken);

      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
      }

      processQueue(null, access_token);
      isRefreshing = false;
      return apiClient(originalRequest);
    } catch (refreshError) {
      await clearTokens();
      processQueue(
        refreshError instanceof Error ? refreshError : new Error('Token refresh failed'),
      );
      isRefreshing = false;
      return Promise.reject(refreshError);
    }
  },
);

export function extractData<T>(response: AxiosResponse<T>): T {
  return response.data;
}

export async function apiGet<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await apiClient.get<T>(url, { params });
  return response.data;
}

/**
 * Options accepted by mutation helpers (P4 — plan P4.B).
 * - headers: passed as Axios request headers (e.g. Idempotency-Key)
 * - timeout: per-request timeout (ms) overriding the global default
 */
export interface ApiRequestOptions {
  headers?: Record<string, string>;
  timeout?: number;
}

export async function apiPost<T>(
  url: string,
  data?: unknown,
  options?: ApiRequestOptions,
): Promise<T> {
  const response = await apiClient.post<T>(url, data, {
    headers: options?.headers,
    timeout: options?.timeout,
  });
  return response.data;
}

/**
 * Same as apiPost but also returns the Axios response so callers can inspect
 * custom headers (e.g. Idempotency-Replay). Use when replay detection is needed.
 */
export async function apiPostRaw<T>(
  url: string,
  data?: unknown,
  options?: ApiRequestOptions,
): Promise<AxiosResponse<T>> {
  return apiClient.post<T>(url, data, {
    headers: options?.headers,
    timeout: options?.timeout,
  });
}

export async function apiPut<T>(
  url: string,
  data?: unknown,
  options?: ApiRequestOptions,
): Promise<T> {
  const response = await apiClient.put<T>(url, data, {
    headers: options?.headers,
    timeout: options?.timeout,
  });
  return response.data;
}

export async function apiPatch<T>(url: string, data?: unknown): Promise<T> {
  const response = await apiClient.patch<T>(url, data);
  return response.data;
}

export async function apiDelete<T>(url: string): Promise<T> {
  const response = await apiClient.delete<T>(url);
  return response.data;
}

export async function apiUpload<T>(
  url: string,
  formData: FormData,
  onUploadProgress?: (progress: number) => void,
): Promise<T> {
  const response = await apiClient.post<T>(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
    onUploadProgress: onUploadProgress
      ? (event) => { if (event.total) onUploadProgress(event.loaded / event.total); }
      : undefined,
  });
  return response.data;
}

export default apiClient;
export { appConfig };
