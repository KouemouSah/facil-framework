/**
 * Axios API Client Configuration
 * Configured for TaxasGE Backend API with automatic token refresh
 *
 * Security:
 * - Access token: read from in-memory store (XSS-safe)
 * - Refresh token: sent via HttpOnly cookie (withCredentials)
 * - Token refresh queue: max 50 requests, 10s timeout
 * - Cross-tab auth sync via BroadcastChannel
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import {
  getAuthData,
  setAuthData,
  clearAuthData,
  getAccessToken,
  setAccessToken,
  setRefreshToken,
} from '@/core/auth/storage';
import { broadcastAuthEvent } from '@/core/auth/broadcast';
import { appConfig } from '@/core/config/app';

// Create axios instance with Cloud Run backend
const apiClient: AxiosInstance = axios.create({
  baseURL: `${appConfig.api.baseUrl}/api/${appConfig.api.version}`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: appConfig.api.timeout,
  withCredentials: true, // Send HttpOnly cookies (refresh_token) automatically
});

// Request interceptor - Add auth token from memory + Accept-Language
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Read access token from memory (NOT localStorage)
    const accessToken = getAccessToken();

    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }

    // Send current locale to backend for localized responses
    if (typeof window !== 'undefined' && config.headers) {
      const pathParts = window.location.pathname.split('/');
      const locale = pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1]) ? pathParts[1] : 'es';
      config.headers['Accept-Language'] = locale;
    }

    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle token refresh
const MAX_QUEUE_SIZE = 50;
const REFRESH_TIMEOUT_MS = 10_000;
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If 401 and not already retrying
    // Skip redirect logic if already on auth pages (prevent redirect loop)
    const isOnAuthPage = typeof window !== 'undefined' && window.location.pathname.includes('/auth');

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Reject if queue is full (prevent memory leak)
        if (failedQueue.length >= MAX_QUEUE_SIZE) {
          return Promise.reject(new Error('Too many pending requests'));
        }
        // Queue this request while refresh is in progress
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => {
            return apiClient(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      // Check we have some auth context (user data in localStorage)
      const authData = getAuthData();
      if (!authData?.user) {
        clearAuthData();
        if (typeof window !== 'undefined' && !isOnAuthPage) {
          const pathParts = window.location.pathname.split('/');
          const locale = pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1]) ? pathParts[1] : 'es';
          window.location.href = `/${locale}/auth`;
        }
        isRefreshing = false;
        return Promise.reject(error);
      }

      try {
        // Refresh token with timeout + AbortController
        // refresh_token is sent via HttpOnly cookie (withCredentials: true)
        // Also send in body for backward compatibility
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS);

        const response = await axios.post(
          `${appConfig.api.baseUrl}/api/${appConfig.api.version}/auth/refresh`,
          { refresh_token: authData.refresh_token || '' },
          {
            headers: { 'Content-Type': 'application/json' },
            signal: controller.signal,
            withCredentials: true, // Send HttpOnly cookie
          }
        );
        clearTimeout(timeout);

        const { access_token, refresh_token, user: refreshedUser } = response.data;

        // Update in-memory tokens
        setAccessToken(access_token);
        setRefreshToken(refresh_token);

        // Update localStorage — merge user data (role_code) from refresh response
        const updatedAuthData = {
          ...authData,
          access_token,
          refresh_token,
        };
        if (refreshedUser && updatedAuthData.user) {
          updatedAuthData.user = { ...updatedAuthData.user, ...refreshedUser };
        }
        setAuthData(updatedAuthData);

        // Broadcast token refresh to other tabs
        broadcastAuthEvent('token-refresh');

        // Update authorization header
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }

        processQueue(null, access_token);
        isRefreshing = false;

        // Retry original request
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError as Error, null);
        clearAuthData();

        if (typeof window !== 'undefined' && !isOnAuthPage) {
          const pathParts = window.location.pathname.split('/');
          const locale = pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1]) ? pathParts[1] : 'es';
          window.location.href = `/${locale}/auth`;
        }

        isRefreshing = false;
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Cross-tab auth sync: if another tab logs out, redirect this tab to login
if (typeof window !== 'undefined') {
  import('@/core/auth/broadcast').then(({ onAuthBroadcast }) => {
    onAuthBroadcast((msg) => {
      if (msg.type === 'logout') {
        // Another tab logged out — clear local state and redirect
        clearAuthData();
        const pathParts = window.location.pathname.split('/');
        const locale = pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1]) ? pathParts[1] : 'es';
        window.location.href = `/${locale}/auth`;
      }
    });
  }).catch(() => { /* SSR or unsupported */ });
}

export default apiClient;
export { appConfig };
