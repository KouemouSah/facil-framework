/**
 * Auth Provider - Facil Inspeccion
 *
 * Manages authentication state with inspector role verification.
 * After login, verifies the user has inspection permissions.
 * Rejects login if user is not an inspection agent/supervisor.
 * HF-1: Enriches profile with agent context from /profiles/me.
 */

import React, { createContext, useCallback, useEffect, useMemo, useState } from 'react';

import { apiGet, apiPost } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import {
  clearAllAuthData,
  getAccessToken,
  getRefreshToken,
  getUserProfile,
  setTokens,
  setUserProfile,
} from '@core/auth/auth-storage';
import { identifyLogRocket } from '@core/observability/logrocket';
import {
  clearBiometricCredentials,
  saveBiometricToken,
  updateBiometricToken,
} from '@core/security/biometric-login';
import type {
  LogoutRequest,
  LogoutResponse,
  TokenRefreshResponse,
  TokenResponse,
  TwoFactorLoginResponse,
  UserProfile,
} from '@core/config/types';

const INSPECTION_PERMISSIONS = [
  'inspection.create',
  'inspection.view_own',
  'inspection.view_entity',
];

export interface AgentContext {
  entityCode: string;
  entityLocationId: string;
  locationCity: string;
  locationRegion: string;
  isMainOffice: boolean;
  ministryId: number | null;
}

export interface AuthContextValue {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isSupervisor: boolean;
  agentContext: AgentContext | null;
  signIn: (email: string, password: string) => Promise<{ requires2fa?: boolean; tempToken?: string }>;
  signInWithBiometric: (refreshToken: string, email: string) => Promise<void>;
  verify2fa: (tempToken: string, code: string) => Promise<void>;
  signOut: (allSessions?: boolean) => Promise<void>;
  refreshProfile: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Enrich a base UserProfile with agent-specific fields from /profiles/me.
 * Fails silently if the user has no agent profile (e.g., citizen on wrong app).
 */
async function enrichWithAgentProfile(base: UserProfile): Promise<UserProfile> {
  try {
    const agent = await apiGet<Record<string, unknown>>(API_ENDPOINTS.agents.profile);
    return {
      ...base,
      entity_location_id: agent.entity_location_id as string | undefined,
      entity_code: agent.entity_code as string | undefined,
      location_city: agent.location_city as string | undefined,
      location_region: agent.location_region as string | undefined,
      is_main_office: agent.is_main_office as boolean | undefined,
      ministry_id: (agent.ministry_id as number) ?? null,
      is_supervisor_agent: agent.is_supervisor as boolean | undefined,
    };
  } catch {
    // /profiles/me may 403/404 if user has no agent profile — not blocking
    return base;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(getUserProfile);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = !!user;
  const isSupervisor = useMemo(() => {
    if (!user?.permissions) return false;
    return user.permissions.includes('inspection.seal_approve') ||
      user.permissions.includes('inspection.view_entity');
  }, [user?.permissions]);

  const agentContext = useMemo<AgentContext | null>(() => {
    if (!user?.entity_code || !user?.entity_location_id) return null;
    return {
      entityCode: user.entity_code,
      entityLocationId: user.entity_location_id,
      locationCity: user.location_city ?? '',
      locationRegion: user.location_region ?? '',
      isMainOffice: user.is_main_office ?? false,
      ministryId: user.ministry_id ?? null,
    };
  }, [user?.entity_code, user?.entity_location_id, user?.location_city, user?.location_region, user?.is_main_office, user?.ministry_id]);

  // LogRocket — attach (non-PII) user context to the active session.
  // id + role + locale only; never email / phone / NIF.
  useEffect(() => {
    if (user) {
      identifyLogRocket({
        id: String(user.id),
        role: user.role,
        locale: user.preferred_language,
      });
    } else if (!isLoading) {
      identifyLogRocket(null);
    }
  }, [user, isLoading]);

  // Bootstrap: check stored tokens on mount
  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const token = await getAccessToken();
        if (!token) {
          if (!cancelled) {
            setUser(null);
            setIsLoading(false);
          }
          return;
        }

        try {
          const profile = await apiGet<UserProfile>(API_ENDPOINTS.users.profile);

          if (!cancelled) {
            // Verify inspection permissions
            const perms = profile.permissions ?? [];
            const hasInspection = perms.some((p) => INSPECTION_PERMISSIONS.includes(p));
            if (!hasInspection) {
              await clearAllAuthData();
              setUser(null);
            } else {
              const enriched = await enrichWithAgentProfile(profile);
              setUserProfile(enriched);
              setUser(enriched);
            }
          }
        } catch {
          // Network timeout or error - use cached profile if available
          if (!cancelled) {
            const cached = getUserProfile();
            if (cached) {
              setUser(cached);
            } else {
              setUser(null);
            }
          }
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    bootstrap();
    return () => { cancelled = true; };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await apiPost<TokenResponse | TwoFactorLoginResponse>(
      API_ENDPOINTS.auth.login,
      { email, password },
    );

    if ('requires_2fa' in response && response.requires_2fa) {
      return { requires2fa: true, tempToken: response.temp_token };
    }

    const tokenResponse = response as TokenResponse;
    const profile = tokenResponse.user;

    // Check inspection permissions
    const perms = profile.permissions ?? [];
    const hasInspection = perms.some((p) => INSPECTION_PERMISSIONS.includes(p));
    if (!hasInspection) {
      throw new Error('Su cuenta no tiene permisos de inspeccion. Contacte al administrador.');
    }

    await setTokens(tokenResponse.access_token, tokenResponse.refresh_token);
    const enriched = await enrichWithAgentProfile(profile);
    setUserProfile(enriched);
    setUser(enriched);

    // Save refresh token for biometric login (not password)
    await saveBiometricToken(email, tokenResponse.refresh_token);

    return {};
  }, []);

  const signInWithBiometric = useCallback(async (refreshToken: string, email: string) => {
    // Use stored refresh token to get new access + refresh tokens
    const response = await apiPost<TokenRefreshResponse>(
      API_ENDPOINTS.auth.refresh,
      { refresh_token: refreshToken },
    );

    const newAccessToken = response.access_token;
    const newRefreshToken = response.refresh_token;

    await setTokens(newAccessToken, newRefreshToken);

    // Fetch full profile with permissions
    const profile = response.user ?? await apiGet<UserProfile>(API_ENDPOINTS.users.profile);

    const perms = profile.permissions ?? [];
    const hasInspection = perms.some((p) => INSPECTION_PERMISSIONS.includes(p));
    if (!hasInspection) {
      await clearAllAuthData();
      await clearBiometricCredentials();
      throw new Error('Su cuenta no tiene permisos de inspeccion. Contacte al administrador.');
    }

    const enriched = await enrichWithAgentProfile(profile);
    setUserProfile(enriched);
    setUser(enriched);

    // Update biometric stored token with the new refresh token
    await updateBiometricToken(newRefreshToken);
  }, []);

  const verify2fa = useCallback(async (tempToken: string, code: string) => {
    const response = await apiPost<TokenResponse>(
      API_ENDPOINTS.auth.login2faVerify,
      { temp_token: tempToken, code },
    );

    const profile = response.user;
    const perms = profile.permissions ?? [];
    const hasInspection = perms.some((p) => INSPECTION_PERMISSIONS.includes(p));
    if (!hasInspection) {
      throw new Error('Su cuenta no tiene permisos de inspeccion. Contacte al administrador.');
    }

    await setTokens(response.access_token, response.refresh_token);
    const enriched = await enrichWithAgentProfile(profile);
    setUserProfile(enriched);
    setUser(enriched);
  }, []);

  const signOut = useCallback(async (allSessions = false) => {
    try {
      const refreshToken = await getRefreshToken();
      const body: LogoutRequest = {
        refresh_token: refreshToken ?? undefined,
        all_sessions: allSessions,
      };
      await apiPost<LogoutResponse>(API_ENDPOINTS.auth.logout, body).catch(() => {});
    } finally {
      await clearBiometricCredentials();
      await clearAllAuthData();
      setUser(null);
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    try {
      const profile = await apiGet<UserProfile>(API_ENDPOINTS.users.profile);
      const enriched = await enrichWithAgentProfile(profile);
      setUserProfile(enriched);
      setUser(enriched);
    } catch {
      // Silent fail - keep current profile
    }
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    isAuthenticated,
    isLoading,
    isSupervisor,
    agentContext,
    signIn,
    signInWithBiometric,
    verify2fa,
    signOut,
    refreshProfile,
  }), [user, isAuthenticated, isLoading, isSupervisor, agentContext, signIn, signInWithBiometric, verify2fa, signOut, refreshProfile]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
