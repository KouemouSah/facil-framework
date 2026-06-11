/**
 * Application Constants
 * Global constants used across the application
 */

export const APP_CONSTANTS = {
  // Storage Keys
  STORAGE_KEYS: {
    AUTH_DATA: 'taxasge_auth',
    LANGUAGE: 'taxasge_language',
    THEME: 'taxasge_theme',
  },

  // API Routes (aligned with backend modules)
  API_ROUTES: {
    AUTH: '/auth',
    USERS: '/users',
    HOMEPAGE: '/homepage',
    FISCAL_SERVICES: '/fiscal-services',
    DECLARATIONS: '/declarations',
    DOCUMENTS: '/documents',
    PAYMENTS: '/payments',
    COMPANIES: '/companies',
    AGENTS: '/agents',
    CHATBOT: '/chatbot',
    COMMUNICATIONS: '/communications',
    TRANSLATIONS: '/translations',
    WEBHOOKS: '/webhooks',
  },

  // User Roles (aligned with backend - MUST match user_role_enum in database)
  // Migration 048: Simplified to 6 roles
  USER_ROLES: {
    CITIZEN: 'citizen',
    BUSINESS: 'business',
    ACCOUNTANT: 'accountant',
    AGENT: 'agent',           // Unified agent role (supervisors via is_supervisor flag)
    FUNCIONARIO: 'funcionario',
    ADMIN: 'admin',
  } as const,

  // User Status (aligned with backend)
  USER_STATUS: {
    ACTIVE: 'active',
    INACTIVE: 'inactive',
    SUSPENDED: 'suspended',
    PENDING_VERIFICATION: 'pending_verification',
  } as const,

  // Declaration Types (aligned with backend - top volume types)
  DECLARATION_TYPES: {
    // IVA (90% volume)
    IVA_DESTAJO: 'iva_destajo',
    IVA_REAL: 'iva_real',

    // IRPF (5% volume)
    INCOME_TAX: 'income_tax',
    CORPORATE_TAX: 'corporate_tax',

    // Petroleum (4% volume, high amounts)
    RETENCION_3PCT_PETROLERO: 'retencion_3pct_petrolero',
    RETENCION_5PCT_PETROLERO: 'retencion_5pct_petrolero',
    RETENCION_10PCT_PETROLERO: 'retencion_10pct_petrolero',
    PETROLEO_GAS: 'petroleo_gas',
    PETROLEO_DIESEL: 'petroleo_diesel',
    PETROLEO_ESSENCE: 'petroleo_essence',
  } as const,

  // Declaration Status (aligned with backend)
  DECLARATION_STATUS: {
    DRAFT: 'draft',
    PENDING: 'pending',
    IN_REVIEW: 'in_review',
    APPROVED: 'approved',
    REJECTED: 'rejected',
    PAID: 'paid',
  } as const,

  // Payment Methods (aligned with backend)
  PAYMENT_METHODS: {
    CASH: 'cash',
    BANK_TRANSFER: 'bank_transfer',
    CARD: 'card',
    MOBILE_MONEY: 'mobile_money',
  } as const,

  // Payment Status (aligned with backend)
  PAYMENT_STATUS: {
    PENDING: 'pending',
    PROCESSING: 'processing',
    COMPLETED: 'completed',
    FAILED: 'failed',
    REFUNDED: 'refunded',
    CANCELLED: 'cancelled',
  } as const,

  // Languages
  LANGUAGES: {
    ES: 'es',
    FR: 'fr',
    EN: 'en',
  } as const,

  // Date Formats
  DATE_FORMATS: {
    SHORT: 'dd/MM/yyyy',
    LONG: 'dd MMMM yyyy',
    WITH_TIME: 'dd/MM/yyyy HH:mm',
    ISO: "yyyy-MM-dd'T'HH:mm:ss",
  } as const,

  // File Upload
  FILE_UPLOAD: {
    MAX_SIZE_MB: 10,
    ALLOWED_TYPES: {
      DOCUMENTS: ['.pdf', '.doc', '.docx'],
      IMAGES: ['.jpg', '.jpeg', '.png', '.webp'],
      SPREADSHEETS: ['.xls', '.xlsx', '.csv'],
    },
  },

  // Pagination
  PAGINATION: {
    DEFAULT_PAGE: 1,
    DEFAULT_PAGE_SIZE: 20,
    PAGE_SIZE_OPTIONS: [10, 20, 50, 100],
  },

  // HTTP Status Codes
  HTTP_STATUS: {
    OK: 200,
    CREATED: 201,
    NO_CONTENT: 204,
    BAD_REQUEST: 400,
    UNAUTHORIZED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    UNPROCESSABLE_ENTITY: 422,
    INTERNAL_SERVER_ERROR: 500,
  } as const,
} as const;

export type UserRole = typeof APP_CONSTANTS.USER_ROLES[keyof typeof APP_CONSTANTS.USER_ROLES];
export type UserStatus = typeof APP_CONSTANTS.USER_STATUS[keyof typeof APP_CONSTANTS.USER_STATUS];
export type DeclarationStatus = typeof APP_CONSTANTS.DECLARATION_STATUS[keyof typeof APP_CONSTANTS.DECLARATION_STATUS];
export type PaymentMethod = typeof APP_CONSTANTS.PAYMENT_METHODS[keyof typeof APP_CONSTANTS.PAYMENT_METHODS];
export type PaymentStatus = typeof APP_CONSTANTS.PAYMENT_STATUS[keyof typeof APP_CONSTANTS.PAYMENT_STATUS];
export type Language = typeof APP_CONSTANTS.LANGUAGES[keyof typeof APP_CONSTANTS.LANGUAGES];
