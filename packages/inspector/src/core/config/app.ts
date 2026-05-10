/**
 * Centralized App Configuration - Facil Inspeccion
 */

import Constants from 'expo-constants';

export const appConfig = {
  app: {
    name: 'Facil Inspeccion',
    version: Constants.expoConfig?.version ?? '1.0.0',
    buildNumber: Constants.expoConfig?.ios?.buildNumber
      ?? Constants.expoConfig?.android?.versionCode?.toString()
      ?? '1',
    scheme: 'facil-inspeccion',
    bundleId: Constants.expoConfig?.ios?.bundleIdentifier ?? 'com.facil.inspeccion',
  },

  api: {
    baseUrl:
      process.env.EXPO_PUBLIC_API_URL
      ?? 'https://taxasge-backend-staging-392159428433.us-central1.run.app',
    version: process.env.EXPO_PUBLIC_API_VERSION ?? 'v1',
    timeout: Number(process.env.EXPO_PUBLIC_API_TIMEOUT) || 30_000,
    retryAttempts: Number(process.env.EXPO_PUBLIC_API_RETRY_ATTEMPTS) || 2,
    retryDelay: 1_000,
  },

  features: {
    biometricAuth: process.env.EXPO_PUBLIC_FEATURE_BIOMETRIC !== 'false',
    pushNotifications: process.env.EXPO_PUBLIC_FEATURE_PUSH !== 'false',
    offlineMode: process.env.EXPO_PUBLIC_FEATURE_OFFLINE === 'true',
  },

  i18n: {
    defaultLanguage: 'es' as const,
    supportedLanguages: ['es', 'fr', 'en'] as const,
  },

  pagination: {
    defaultPageSize: 20,
    maxPageSize: 100,
  },

  upload: {
    maxFileSizeMB: 10,
    maxImageDimensionPx: 1280,   // Reduced from 1920 — sufficient for inspection evidence
    compressionQuality: 0.6,    // Reduced from 0.7 — saves ~30% bandwidth per photo
    allowedImageTypes: ['image/jpeg', 'image/png'] as const,
  },

  auth: {
    accessTokenTTL: 30 * 60,
    refreshTokenTTL: 30 * 24 * 60 * 60,
    refreshBufferSeconds: 60,
  },

  cache: {
    userProfile: 5 * 60 * 1_000,
    inspections: 1 * 60 * 1_000,
    dashboard: 2 * 60 * 1_000,
    liveStatus: 30 * 1_000,
    translations: 60 * 60 * 1_000,
  },

  validation: {
    maxNotesLength: 2000,
    maxActivityLength: 200,
    maxPaymentNotesLength: 500,
    maxPhoneLength: 15,
    minSearchLength: 3,
  },

  business: {
    phonePrefix: '+240',
    phoneRegex: /^\+240[0-9]{9}$/,
    maxFieldCollectionAmount: 50_000_000,
    medDeadlineMinHours: 24,
    medDeadlineMaxHours: 720,
    medDeadlineDefaultHours: 72,
    maxPhotosPerInspection: 10,
    recentInspectionsCount: 5,
  },
} as const;
