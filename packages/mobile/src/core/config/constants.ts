/**
 * Application Constants
 *
 * All enum constants matching the backend database enums.
 * Used for type-safe comparisons and UI rendering.
 *
 * IMPORTANT: Keep in sync with backend enums in:
 * - Database schema (user_role_enum, declaration_status_enum, etc.)
 * - packages/backend/app/modules/auth/models/auth_models.py
 *
 * When adding new constants, verify they exist in the database first:
 *   SELECT enum_range(NULL::user_role_enum);
 */

// ---------------------------------------------------------------------------
// User Enums
// ---------------------------------------------------------------------------

export const USER_ROLES = {
  CITIZEN: 'citizen',
  BUSINESS: 'business',
  ACCOUNTANT: 'accountant',
  ADMIN: 'admin',
  SUPERVISOR: 'supervisor',
  DGI_AGENT: 'dgi_agent',
  MINISTRY_AGENT: 'ministry_agent',
} as const;

export const USER_STATUS = {
  ACTIVE: 'active',
  SUSPENDED: 'suspended',
  PENDING_VERIFICATION: 'pending_verification',
  DEACTIVATED: 'deactivated',
} as const;

// ---------------------------------------------------------------------------
// Declaration Enums
// ---------------------------------------------------------------------------

export const DECLARATION_STATUS = {
  DRAFT: 'draft',
  SUBMITTED: 'submitted',
  PROCESSING: 'processing',
  ACCEPTED: 'accepted',
  REJECTED: 'rejected',
  AMENDED: 'amended',
} as const;

export const DECLARATION_TYPES = {
  INCOME_TAX: 'income_tax',
  CORPORATE_TAX: 'corporate_tax',
  VAT_DECLARATION: 'vat_declaration',
  IVA_DESTAJO: 'iva_destajo',
  IVA_REAL: 'iva_real',
  RETENCION_ALQUILERES: 'retencion_alquileres',
  RETENCION_SALARIOS: 'retencion_salarios',
  RETENCION_CAPITAL: 'retencion_capital',
  RETENCION_ACTIVIDADES: 'retencion_actividades',
  IMP_TRANSMISIONES: 'imp_transmisiones',
  IMP_ACTOS_JURIDICOS: 'imp_actos_juridicos',
  IMP_PETROLIFEROS: 'imp_petroliferos',
  IMP_SOCIEDADES: 'imp_sociedades',
  IMP_ESPECIAL: 'imp_especial',
  CUOTA_MIN_IRPF: 'cuota_min_irpf',
  CUOTA_MIN_IS: 'cuota_min_is',
  IMPRESO_PAGO: 'impreso_pago',
  IMPRESO_DEUDA: 'impreso_deuda',
} as const;

// ---------------------------------------------------------------------------
// Payment Enums
// ---------------------------------------------------------------------------

export const PAYMENT_STATUS = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  REFUNDED: 'refunded',
  CANCELLED: 'cancelled',
} as const;

export const PAYMENT_METHODS = {
  BANK_TRANSFER: 'bank_transfer',
  CARD: 'card',
  MOBILE_MONEY: 'mobile_money',
  CASH: 'cash',
  BANGE_WALLET: 'bange_wallet',
} as const;

export const PAYMENT_TYPES = {
  FULL: 'full',
  PARTIAL: 'partial',
  INSTALLMENT: 'installment',
  COMPLEMENTARY: 'complementary',
} as const;

export const PAYMENT_WORKFLOW_STATUS = {
  SUBMITTED: 'submitted',
  AUTO_PROCESSING: 'auto_processing',
  PENDING_AGENT_REVIEW: 'pending_agent_review',
  LOCKED_BY_AGENT: 'locked_by_agent',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  COMPLETED: 'completed',
} as const;

// ---------------------------------------------------------------------------
// Service Enums
// ---------------------------------------------------------------------------

export const SERVICE_STATUS = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  DRAFT: 'draft',
  DEPRECATED: 'deprecated',
} as const;

export const SERVICE_TYPES = {
  DOCUMENT_PROCESSING: 'document_processing',
  LICENSE_PERMIT: 'license_permit',
  RESIDENCE_PERMIT: 'residence_permit',
  REGISTRATION_FEE: 'registration_fee',
  INSPECTION_FEE: 'inspection_fee',
  ADMINISTRATIVE_TAX: 'administrative_tax',
  CUSTOMS_DUTY: 'customs_duty',
  DECLARATION_TAX: 'declaration_tax',
} as const;

export const CALCULATION_METHODS = {
  FIXED_EXPEDITION: 'fixed_expedition',
  FIXED_RENEWAL: 'fixed_renewal',
  PERCENTAGE_BASED: 'percentage_based',
  UNIT_BASED: 'unit_based',
  TIERED_RATES: 'tiered_rates',
  FORMULA_BASED: 'formula_based',
  FIXED_PLUS_UNIT: 'fixed_plus_unit',
} as const;

// ---------------------------------------------------------------------------
// Agent Enums
// ---------------------------------------------------------------------------

export const AGENT_ACTIONS = {
  LOCK_FOR_REVIEW: 'lock_for_review',
  APPROVE: 'approve',
  REJECT: 'reject',
  REQUEST_DOCUMENTS: 'request_documents',
  ESCALATE: 'escalate',
  UNLOCK_RELEASE: 'unlock_release',
  ASSIGN_TO_COLLEAGUE: 'assign_to_colleague',
} as const;

export const AGENT_AVAILABILITY = {
  AVAILABLE: 'available',
  ON_LEAVE: 'on_leave',
  SICK_LEAVE: 'sick_leave',
  TRAINING: 'training',
  MISSION: 'mission',
  TEMPORARILY_UNAVAILABLE: 'temporarily_unavailable',
} as const;

export const WORKLOAD_STATUS = {
  AVAILABLE: 'available',
  NORMAL: 'normal',
  BUSY: 'busy',
  OVERLOADED: 'overloaded',
  UNAVAILABLE: 'unavailable',
} as const;

export const ASSIGNMENT_STATUS = {
  ASSIGNED: 'assigned',
  IN_PROGRESS: 'in_progress',
  PENDING_REVIEW: 'pending_review',
  COMPLETED: 'completed',
  REASSIGNED: 'reassigned',
  CANCELLED: 'cancelled',
  REJECTED: 'rejected',
} as const;

export const ESCALATION_LEVELS = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
} as const;

// ---------------------------------------------------------------------------
// Company Enums
// ---------------------------------------------------------------------------

export const COMPANY_ROLES = {
  OWNER: 'company_owner',
  ADMIN: 'company_admin',
  ACCOUNTANT: 'company_accountant',
  MEMBER: 'company_member',
} as const;

// ---------------------------------------------------------------------------
// Communication Enums
// ---------------------------------------------------------------------------

export const COMMUNICATION_PROVIDERS = {
  SMS: 'sms',
  EMAIL: 'email',
  PUSH: 'push',
  WHATSAPP: 'whatsapp',
} as const;

// ---------------------------------------------------------------------------
// i18n
// ---------------------------------------------------------------------------

export const SUPPORTED_LANGUAGES = ['es', 'fr', 'en'] as const;

export const LANGUAGE_LABELS: Record<typeof SUPPORTED_LANGUAGES[number], string> = {
  es: 'Espanol',
  fr: 'Francais',
  en: 'English',
} as const;

// ---------------------------------------------------------------------------
// Citizen-visible notification action types
// ---------------------------------------------------------------------------

export const CITIZEN_VISIBLE_ACTIONS = [
  'STATUS_CHANGE',
  'AGENT_ACTION',
  'COMMENT_ADDED',
  'CITA_SCHEDULED',
  'PAYMENT_RECEIVED',
  'VALIDATION_FAILED',
] as const;
