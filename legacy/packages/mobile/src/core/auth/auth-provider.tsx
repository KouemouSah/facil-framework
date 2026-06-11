/**
 * Auth Provider
 *
 * React Context provider managing authentication state for the Facil mobile app.
 *
 * Responsibilities:
 * - Bootstrap auth state on app launch (check stored tokens)
 * - Sign in / sign up / sign out flows
 * - Automatic token validation on mount
 * - Refresh token rotation on expired access token
 * - Sync user profile to MMKV for fast access
 *
 * Security considerations (OWASP MASVS):
 * - Tokens stored in platform keychain via SecureStore
 * - Token validation on every cold start (no stale sessions)
 * - Refresh failure = forced sign out (no silent degradation)
 * - 2FA flow supported via temp_token exchange
 */

import React, {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import axios from 'axios';
import { useQueryClient } from '@tanstack/react-query';

import { API_ENDPOINTS } from '@core/api/endpoints';
import { appConfig } from '@core/config/app';
import { extractApiError } from '@core/api/errors';
import {
  clearAllAuthData,
  getAccessToken,
  getRefreshToken,
  getUserProfile,
  setTokens,
  setUserProfile,
} from '@core/auth/auth-storage';
import { clearBiometricCredentials } from '@core/security/biometric-login';
import { setSentryUser } from '@core/observability/sentry';
import { identifyLogRocket } from '@core/observability/logrocket';
import { reportDeviceIntegrity } from '@core/security/device-integrity';
import type {
  RegisterData,
  TokenRefreshResponse,
  TokenResponse,
  TwoFactorLoginResponse,
  UserProfile,
} from '@core/config/types';

// ---------------------------------------------------------------------------
// Lazy API client import
// ---------------------------------------------------------------------------

/**
 * We lazily import apiClient to avoid circular dependencies.
 * auth-storage is imported by the API interceptor, which is imported by apiClient.
 * By using a dynamic getter, we break the circular chain.
 *
 * Note: apiClient is the default export from @core/api/client.
 */
// Static import — avoids dynamic import() overhead during bootstrap
import apiClient from '@core/api/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthState {
  /** Current user profile, or null if not authenticated */
  user: UserProfile | null;
  /** Whether the user is fully authenticated (valid tokens + profile) */
  isAuthenticated: boolean;
  /** True during the initial token validation check on app launch */
  isLoading: boolean;
}

/** Result of signIn - either full success or 2FA required */
type SignInResult =
  | { type: 'success' }
  | { type: 'requires_2fa'; tempToken: string };

interface AuthContextValue extends AuthState {
  /** Sign in with email + password. May return 'requires_2fa'. */
  signIn: (email: string, password: string) => Promise<SignInResult>;
  /** Complete 2FA verification after signIn returned 'requires_2fa'. */
  verify2FA: (tempToken: string, code: string) => Promise<void>;
  /** Register a new account. Requires prior email verification. */
  signUp: (data: RegisterData) => Promise<void>;
  /** Sign out: clear tokens, revoke session(s), reset state. */
  signOut: (allSessions?: boolean) => Promise<void>;
  /** Re-fetch user profile from the server (e.g., after settings change). */
  refreshUser: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

export const AuthContext = createContext<AuthContextValue | null>(null);
function getApiClient() {
  return apiClient;
}

// ---------------------------------------------------------------------------
// Provider Component
// ---------------------------------------------------------------------------

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Prevent concurrent refresh attempts
  const isRefreshing = useRef(false);

  // -------------------------------------------------------------------
  // Bootstrap: validate stored tokens on mount
  // -------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const BOOTSTRAP_TIMEOUT_MS = 8000; // Max 8s for bootstrap — after that, show app with cached profile or guest

      try {
        const accessToken = await getAccessToken();

        if (!accessToken) {
          if (!cancelled) {
            setState({ user: null, isAuthenticated: false, isLoading: false });
          }
          return;
        }

        // Try cached profile + quick token validation
        const cachedProfile = getUserProfile();
        if (cachedProfile && !cancelled) {
          // Show app immediately with cached data
          setState({ user: cachedProfile, isAuthenticated: true, isLoading: false });

          // Validate token in background — if expired, force logout immediately
          const client = getApiClient();
          client
            .get<UserProfile>(API_ENDPOINTS.users.profile, { timeout: BOOTSTRAP_TIMEOUT_MS })
            .then((res) => {
              if (!cancelled) {
                setUserProfile(res.data);
                setState((prev) => ({ ...prev, user: res.data }));
              }
            })
            .catch(async (err) => {
              if (cancelled) return;
              const status = err?.response?.status;
              // 401/403 = token expired → force logout
              // Also logout if refresh token was used and still failed (interceptor clears tokens)
              if (status === 401 || status === 403) {
                await clearAllAuthData();
                await clearBiometricCredentials();
                setState({ user: null, isAuthenticated: false, isLoading: false });
              }
              // Network error (timeout, offline) → keep cached profile
            });
          return;
        }

        // No cached profile — must fetch from network (with timeout)
        const client = await getApiClient();
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), BOOTSTRAP_TIMEOUT_MS);

        try {
          const response = await client.get<UserProfile>(API_ENDPOINTS.users.profile, {
            signal: controller.signal,
            timeout: BOOTSTRAP_TIMEOUT_MS,
          });
          clearTimeout(timeoutId);
          const profile = response.data;
          setUserProfile(profile);

          if (!cancelled) {
            setState({ user: profile, isAuthenticated: true, isLoading: false });
          }
        } catch {
          clearTimeout(timeoutId);

          // If aborted (timeout), go to guest mode
          if (controller.signal.aborted) {
            if (!cancelled) {
              setState({ user: null, isAuthenticated: false, isLoading: false });
            }
            return;
          }

          // Access token might be expired — try refresh (with timeout)
          const refreshed = await attemptTokenRefresh();

          if (refreshed && !cancelled) {
            try {
              const retryResponse = await client.get<UserProfile>(API_ENDPOINTS.users.profile, {
                timeout: BOOTSTRAP_TIMEOUT_MS,
              });
              const profile = retryResponse.data;
              setUserProfile(profile);
              setState({ user: profile, isAuthenticated: true, isLoading: false });
            } catch {
              await clearAllAuthData();
              setState({ user: null, isAuthenticated: false, isLoading: false });
            }
          } else if (!cancelled) {
            await clearAllAuthData();
            setState({ user: null, isAuthenticated: false, isLoading: false });
          }
        }
      } catch {
        if (!cancelled) {
          await clearAllAuthData();
          setState({ user: null, isAuthenticated: false, isLoading: false });
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  // -------------------------------------------------------------------
  // Token Refresh
  // -------------------------------------------------------------------

  async function attemptTokenRefresh(): Promise<boolean> {
    if (isRefreshing.current) return false;
    isRefreshing.current = true;

    try {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) return false;

      // Use raw axios (not apiClient) to avoid response interceptors
      // triggering another refresh cycle on 401.
      const refreshUrl = `${appConfig.api.baseUrl}/api/${appConfig.api.version}${API_ENDPOINTS.auth.refresh}`;
      const response = await axios.post<TokenRefreshResponse>(
        refreshUrl,
        { refresh_token: refreshToken },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 10_000,
        },
      );

      const { access_token, refresh_token } = response.data;
      await setTokens(access_token, refresh_token);

      // If the server returned updated user data, cache it
      if (response.data.user) {
        const cachedProfile = getUserProfile();
        if (cachedProfile) {
          const updatedProfile: UserProfile = {
            ...cachedProfile,
            ...(response.data.user as Partial<UserProfile>),
          };
          setUserProfile(updatedProfile);
        }
      }

      return true;
    } catch {
      return false;
    } finally {
      isRefreshing.current = false;
    }
  }

  // -------------------------------------------------------------------
  // Sign In
  // -------------------------------------------------------------------

  const signIn = useCallback(
    async (email: string, password: string): Promise<SignInResult> => {
      const client = await getApiClient();

      const response = await client.post<TokenResponse | TwoFactorLoginResponse>(
        API_ENDPOINTS.auth.login,
        { email, password },
      );

      const data = response.data;

      // Check if 2FA is required
      if ('requires_2fa' in data && data.requires_2fa) {
        return { type: 'requires_2fa', tempToken: data.temp_token };
      }

      // Standard login - store tokens and fetch profile
      const tokenData = data as TokenResponse;
      await setTokens(tokenData.access_token, tokenData.refresh_token);

      // Fetch full profile from /users/profile for complete data
      const profileResponse = await client.get<UserProfile>(API_ENDPOINTS.users.profile);
      const profile = profileResponse.data;

      setUserProfile(profile);
      setState({ user: profile, isAuthenticated: true, isLoading: false });

      return { type: 'success' };
    },
    [],
  );

  // -------------------------------------------------------------------
  // 2FA Verification
  // -------------------------------------------------------------------

  const verify2FA = useCallback(
    async (tempToken: string, code: string): Promise<void> => {
      const client = await getApiClient();

      const response = await client.post<TokenResponse>(
        API_ENDPOINTS.auth.login2faVerify,
        { temp_token: tempToken, code },
      );

      await setTokens(response.data.access_token, response.data.refresh_token);

      // Fetch full profile
      const profileResponse = await client.get<UserProfile>(API_ENDPOINTS.users.profile);
      const profile = profileResponse.data;

      setUserProfile(profile);
      setState({ user: profile, isAuthenticated: true, isLoading: false });
    },
    [],
  );

  // -------------------------------------------------------------------
  // Sign Up
  // -------------------------------------------------------------------

  const signUp = useCallback(
    async (data: RegisterData): Promise<void> => {
      const client = await getApiClient();

      const response = await client.post<TokenResponse>(
        API_ENDPOINTS.auth.register,
        data,
      );

      await setTokens(response.data.access_token, response.data.refresh_token);

      // Fetch full profile
      const profileResponse = await client.get<UserProfile>(API_ENDPOINTS.users.profile);
      const profile = profileResponse.data;

      setUserProfile(profile);
      setState({ user: profile, isAuthenticated: true, isLoading: false });
    },
    [],
  );

  // -------------------------------------------------------------------
  // Sign Out
  // -------------------------------------------------------------------

  const signOut = useCallback(async (allSessions = false): Promise<void> => {
    try {
      const refreshToken = await getRefreshToken();
      const client = await getApiClient();

      // Best-effort server-side session revocation
      await client
        .post(API_ENDPOINTS.auth.logout, {
          refresh_token: refreshToken,
          all_sessions: allSessions,
        })
        .catch(() => {
          // Ignore logout API failures - we clear local state regardless
        });
    } catch {
      // Network error during logout - proceed with local cleanup
    } finally {
      await clearAllAuthData();
      await clearBiometricCredentials();
      // Clear the React Query cache (in-memory + persisted MMKV bucket).
      // Without this, the next user's cold start would briefly read the
      // previous user's whitelisted entries from MMKV (dashboard,
      // service-requests). `queryClient.clear()` removes everything from the
      // in-memory cache; the next persistClient cycle on the empty store
      // overwrites the persisted bucket with an empty PersistedClient.
      queryClient.clear();
      setState({ user: null, isAuthenticated: false, isLoading: false });
    }
  }, [queryClient]);

  // -------------------------------------------------------------------
  // Refresh User Profile
  // -------------------------------------------------------------------

  const refreshUser = useCallback(async (): Promise<void> => {
    try {
      const client = await getApiClient();
      const response = await client.get<UserProfile>(API_ENDPOINTS.users.profile);
      const profile = response.data;

      setUserProfile(profile);
      setState((prev) => ({ ...prev, user: profile }));
    } catch (error) {
      const apiError = extractApiError(error);
      if (apiError.isAuthError) {
        await clearAllAuthData();
        setState({ user: null, isAuthenticated: false, isLoading: false });
      }
      // Non-auth errors: keep current state (stale profile is better than none)
    }
  }, []);

  // -------------------------------------------------------------------
  // Sentry user context — keep in sync with the auth state.
  // No PII (no email, no phone) — only id / role / preferred_language.
  // -------------------------------------------------------------------

  // Track the previous authenticated user id so we can detect a *new* login
  // (vs. just a profile refresh) and re-run the device integrity check.
  const lastReportedUserIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (state.user) {
      const id = String(state.user.id);
      const role = state.user.role;
      const locale = state.user.preferred_language ?? undefined;
      setSentryUser({ id, role, locale });
      identifyLogRocket({ id, role, locale });
      // Refire device integrity on every fresh login (different user id, or
      // first sign-in this session). Cold-start case is still covered by
      // <DeferredEffects /> in the root layout — together they cover both
      // "first launch" and "user switched account".
      if (lastReportedUserIdRef.current !== id) {
        lastReportedUserIdRef.current = id;
        void reportDeviceIntegrity();
      }
    } else if (!state.isLoading) {
      setSentryUser(null);
      identifyLogRocket(null);
      lastReportedUserIdRef.current = null;
    }
  }, [state.user, state.isLoading]);

  // -------------------------------------------------------------------
  // Context Value (memoized to prevent unnecessary re-renders)
  // -------------------------------------------------------------------

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      signIn,
      verify2FA,
      signUp,
      signOut,
      refreshUser,
    }),
    [state, signIn, verify2FA, signUp, signOut, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
