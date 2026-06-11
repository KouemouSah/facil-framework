/**
 * Centralized App Configuration
 *
 * All configuration values are sourced from environment variables
 * (prefixed with EXPO_PUBLIC_ for client-side access in Expo).
 *
 * Defaults are provided for development; production values come from
 * EAS build profiles or .env files.
 *
 * IMPORTANT: Never put secrets here. This file is bundled into the app binary.
 * Use expo-secure-store for runtime secrets (tokens, keys).
 */

import Constants from 'expo-constants';

export const appConfig = {
  // ---------------------------------------------------------------------------
  // App Metadata
  // ---------------------------------------------------------------------------
  app: {
    name: 'Facil',
    version: Constants.expoConfig?.version ?? '1.0.0',
    buildNumber: Constants.expoConfig?.ios?.buildNumber
      ?? Constants.expoConfig?.android?.versionCode?.toString()
      ?? '1',
    scheme: 'facil',
    bundleId: Constants.expoConfig?.ios?.bundleIdentifier ?? 'com.facil.app',
  },

  // ---------------------------------------------------------------------------
  // API Configuration
  // ---------------------------------------------------------------------------
  api: {
    /**
     * Base URL for the backend (host only, WITHOUT /api/v1 suffix).
     * The full URL is constructed as: `${baseUrl}/api/${version}`
     * by the API client in @core/api/client.ts.
     */
    baseUrl:
      process.env.EXPO_PUBLIC_API_URL
      ?? (__DEV__ ? 'https://taxasge-backend-staging-392159428433.us-central1.run.app' : ''),
    /** API version prefix (appended as /api/{version}) */
    version: process.env.EXPO_PUBLIC_API_VERSION ?? 'v1',
    /** Request timeout in milliseconds */
    timeout: Number(process.env.EXPO_PUBLIC_API_TIMEOUT) || 30_000,
    /** Number of retry attempts for failed requests (network errors only) */
    retryAttempts: Number(process.env.EXPO_PUBLIC_API_RETRY_ATTEMPTS) || 2,
    /** Delay between retries in milliseconds (exponential backoff base) */
    retryDelay: 1_000,
  },

  // ---------------------------------------------------------------------------
  // Feature Flags
  // ---------------------------------------------------------------------------
  features: {
    /** Enable biometric authentication (Face ID / fingerprint) */
    biometricAuth: process.env.EXPO_PUBLIC_FEATURE_BIOMETRIC !== 'false',
    /** Enable push notifications */
    pushNotifications: process.env.EXPO_PUBLIC_FEATURE_PUSH !== 'false',
    /** Enable AI chatbot (RAG + Gemini) */
    chatbot: process.env.EXPO_PUBLIC_FEATURE_CHATBOT !== 'false',
    /** Enable offline mode with local queue */
    offlineMode: process.env.EXPO_PUBLIC_FEATURE_OFFLINE === 'true',
  },

  // ---------------------------------------------------------------------------
  // Internationalization
  // ---------------------------------------------------------------------------
  i18n: {
    defaultLanguage: 'es' as const,
    supportedLanguages: ['es', 'fr', 'en'] as const,
  },

  // ---------------------------------------------------------------------------
  // Pagination
  // ---------------------------------------------------------------------------
  pagination: {
    defaultPageSize: 20,
    maxPageSize: 100,
  },

  // ---------------------------------------------------------------------------
  // Upload Constraints
  // ---------------------------------------------------------------------------
  upload: {
    /** Maximum file size in megabytes */
    maxFileSizeMB: 10,
    /** Maximum image dimension (width or height) in pixels before compression */
    maxImageDimensionPx: 2048,
    /** JPEG compression quality (0-1) */
    compressionQuality: 0.8,
    /** Allowed MIME types for image uploads */
    allowedImageTypes: ['image/jpeg', 'image/png', 'image/webp'] as const,
    /** Allowed MIME types for document uploads */
    allowedDocTypes: ['application/pdf', 'image/jpeg', 'image/png'] as const,
  },

  // ---------------------------------------------------------------------------
  // Auth Timing
  // ---------------------------------------------------------------------------
  auth: {
    /** Access token lifetime in seconds (must match backend: 30 min) */
    accessTokenTTL: 30 * 60,
    /** Refresh token lifetime in seconds (must match backend: 30 days) */
    refreshTokenTTL: 30 * 24 * 60 * 60,
    /** Refresh the access token this many seconds before expiry */
    refreshBufferSeconds: 60,
  },

  // ---------------------------------------------------------------------------
  // Cache TTLs (in milliseconds, for React Query staleTime)
  // ---------------------------------------------------------------------------
  cache: {
    /** User profile stale time */
    userProfile: 5 * 60 * 1_000,
    /** Fiscal services catalog stale time */
    fiscalServices: 60 * 60 * 1_000,
    /** Translations stale time */
    translations: 60 * 60 * 1_000,
    /** Dashboard summary stale time */
    dashboardSummary: 2 * 60 * 1_000,
    /** Service request list stale time */
    serviceRequests: 1 * 60 * 1_000,
  },
} as const;
