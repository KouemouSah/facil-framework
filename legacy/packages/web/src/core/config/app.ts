/**
 * Application Configuration
 * Central configuration for Facil Frontend (Cloud Run deployment)
 */

export const appConfig = {
  // Application metadata
  app: {
    name: process.env.NEXT_PUBLIC_APP_NAME || 'Facil',
    version: process.env.NEXT_PUBLIC_APP_VERSION || '1.0.0',
    environment: process.env.NEXT_PUBLIC_ENVIRONMENT || 'development',
  },

  // API Configuration
  // Note: NEXT_PUBLIC_API_URL is set by GitHub Actions deployment workflow
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'https://taxasge-backend-dev.run.app',
    version: process.env.NEXT_PUBLIC_API_VERSION || 'v1',
    timeout: parseInt(process.env.NEXT_PUBLIC_API_TIMEOUT || '30000', 10),
  },

  // Site Configuration
  site: {
    url: process.env.NEXT_PUBLIC_SITE_URL || 'https://taxasge-frontend-dev.run.app',
    name: process.env.NEXT_PUBLIC_SITE_NAME || 'Facil',
    description: process.env.NEXT_PUBLIC_SITE_DESCRIPTION || 'Plataforma Digital AI de Tramites de Guinea Ecuatorial',
    keywords: process.env.NEXT_PUBLIC_SITE_KEYWORDS || 'tramites,guinea ecuatorial,servicios,gobierno,digital',
  },

  // Feature Flags
  features: {
    pwa: process.env.NEXT_PUBLIC_ENABLE_PWA === 'true',
    offlineMode: process.env.NEXT_PUBLIC_ENABLE_OFFLINE_MODE === 'true',
    analytics: process.env.NEXT_PUBLIC_ENABLE_ANALYTICS === 'true',
    seo: process.env.NEXT_PUBLIC_ENABLE_SEO === 'true',
    i18n: process.env.NEXT_PUBLIC_ENABLE_I18N === 'true',
    search: process.env.NEXT_PUBLIC_ENABLE_SEARCH === 'true',
    chatbot: process.env.NEXT_PUBLIC_ENABLE_CHATBOT === 'true',
  },

  // Internationalization
  i18n: {
    defaultLanguage: process.env.NEXT_PUBLIC_DEFAULT_LANGUAGE || 'es',
    supportedLanguages: (process.env.NEXT_PUBLIC_SUPPORTED_LANGUAGES || 'es,fr,en').split(','),
  },

  // Authentication
  auth: {
    tokenKey: process.env.NEXT_PUBLIC_AUTH_TOKEN_KEY || 'taxasge_auth_token',
    refreshTokenKey: process.env.NEXT_PUBLIC_AUTH_REFRESH_TOKEN_KEY || 'taxasge_refresh_token',
    sessionTimeout: parseInt(process.env.NEXT_PUBLIC_SESSION_TIMEOUT || '30', 10), // minutes
  },

  // Pagination & Limits
  pagination: {
    defaultPageSize: parseInt(process.env.NEXT_PUBLIC_DEFAULT_PAGE_SIZE || '20', 10),
    maxUploadSizeMB: parseInt(process.env.NEXT_PUBLIC_MAX_UPLOAD_SIZE_MB || '10', 10),
  },

  // Analytics
  analytics: {
    googleAnalyticsId: process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || '',
  },

  // Error Tracking
  monitoring: {
    sentryDsn: process.env.NEXT_PUBLIC_SENTRY_DSN || '',
  },

  // External Services
  external: {
    firebase: {
      projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'taxasge-dev',
      storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || 'taxasge-dev.firebasestorage.app',
    },
  },

  // Development
  dev: {
    debug: process.env.NEXT_PUBLIC_DEBUG === 'true',
    reactQueryDevTools: process.env.NEXT_PUBLIC_ENABLE_REACT_QUERY_DEVTOOLS === 'true',
    mockApi: process.env.NEXT_PUBLIC_MOCK_API === 'true',
  },
} as const;

export type AppConfig = typeof appConfig;
