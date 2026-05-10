/**
 * Fiscal Services Types - 100% Aligned with Backend Pydantic Models
 *
 * Backend Reference: packages/backend/app/modules/fiscal_services/models/
 * - fiscal_service.py (414 lines)
 * - templates.py (402 lines)
 *
 * Database Tables: 12 tables
 * - fiscal_services, ministries, sectors, categories
 * - document_templates, procedure_templates, procedure_template_steps
 * - service_document_assignments, service_procedure_assignments
 * - service_keywords, entity_translations
 *
 * @module types/fiscal-service
 * @author Claude Code
 * @date 2025-11-25
 */

// =============================================================================
// ENUMS - Aligned with Backend Exact Values
// =============================================================================

export enum ServiceTypeEnum {
  DOCUMENT_PROCESSING = 'document_processing',
  LICENSE_PERMIT = 'license_permit',
  RESIDENCE_PERMIT = 'residence_permit',
  REGISTRATION_FEE = 'registration_fee',
  INSPECTION_FEE = 'inspection_fee',
  ADMINISTRATIVE_TAX = 'administrative_tax',
  CUSTOMS_DUTY = 'customs_duty',
  DECLARATION_TAX = 'declaration_tax',
}

export enum CalculationMethodEnum {
  FIXED_EXPEDITION = 'fixed_expedition',     // Fixed fee for first issuance
  FIXED_RENEWAL = 'fixed_renewal',           // Fixed fee for renewal only
  FIXED_BOTH = 'fixed_both',                 // Same fixed fee for both
  PERCENTAGE_BASED = 'percentage_based',     // Percentage of a value
  UNIT_BASED = 'unit_based',                 // Price per unit
  TIERED_RATES = 'tiered_rates',             // Progressive brackets
  FORMULA_BASED = 'formula_based',           // Custom formula
  FIXED_PLUS_UNIT = 'fixed_plus_unit',       // Base + per-unit charge
}

export enum ServiceStatusEnum {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  DRAFT = 'draft',
  DEPRECATED = 'deprecated',
}

export enum TranslatableEntityType {
  MINISTRY = 'ministry',
  SECTOR = 'sector',
  CATEGORY = 'category',
  FISCAL_SERVICE = 'fiscal_service',
  DOCUMENT_TEMPLATE = 'document_template',
  PROCEDURE_TEMPLATE = 'procedure_template',
  PROCEDURE_STEP = 'procedure_step',
}

// =============================================================================
// HIERARCHY INTERFACES
// =============================================================================

export interface Ministry {
  id: number
  ministry_code: string
  ministryCode?: string  // camelCase alias after transformKeys
  name_es: string
  nameEs?: string        // camelCase alias after transformKeys
  name_fr?: string
  nameFr?: string        // camelCase alias after transformKeys
  name_en?: string
  nameEn?: string        // camelCase alias after transformKeys
  description_es?: string
  descriptionEs?: string // camelCase alias after transformKeys
  description_fr?: string
  descriptionFr?: string // camelCase alias after transformKeys
  description_en?: string
  descriptionEn?: string // camelCase alias after transformKeys
  display_order?: number
  displayOrder?: number  // camelCase alias after transformKeys
  icon?: string
  color?: string
  website_url?: string
  websiteUrl?: string    // camelCase alias after transformKeys
  contact_email?: string
  contactEmail?: string  // camelCase alias after transformKeys
  contact_phone?: string
  contactPhone?: string  // camelCase alias after transformKeys
  is_active: boolean
  isActive?: boolean     // camelCase alias after transformKeys
  description_source?: string
  descriptionSource?: string  // camelCase alias after transformKeys
  created_at: string
  createdAt?: string     // camelCase alias after transformKeys
  updated_at?: string
  updatedAt?: string     // camelCase alias after transformKeys
}

export interface Sector {
  id: number
  sector_code: string
  sectorCode?: string    // camelCase alias after transformKeys
  ministry_id: number
  ministryId?: number    // camelCase alias after transformKeys
  name_es: string
  nameEs?: string        // camelCase alias after transformKeys
  name_fr?: string
  nameFr?: string        // camelCase alias after transformKeys
  name_en?: string
  nameEn?: string        // camelCase alias after transformKeys
  description_es?: string
  descriptionEs?: string // camelCase alias after transformKeys
  description_fr?: string
  descriptionFr?: string // camelCase alias after transformKeys
  description_en?: string
  descriptionEn?: string // camelCase alias after transformKeys
  display_order?: number
  displayOrder?: number  // camelCase alias after transformKeys
  icon?: string
  color?: string
  is_active: boolean
  isActive?: boolean     // camelCase alias after transformKeys
  created_at: string
  createdAt?: string     // camelCase alias after transformKeys
  updated_at?: string
  updatedAt?: string     // camelCase alias after transformKeys
}

export interface Category {
  id: number
  category_code: string
  categoryCode?: string  // camelCase alias after transformKeys
  sector_id?: number
  sectorId?: number      // camelCase alias after transformKeys
  ministry_id?: number
  ministryId?: number    // camelCase alias after transformKeys
  service_type?: ServiceTypeEnum
  serviceType?: ServiceTypeEnum // camelCase alias after transformKeys
  name_es: string
  nameEs?: string        // camelCase alias after transformKeys
  name?: string          // fallback for generic name
  name_fr?: string
  nameFr?: string        // camelCase alias after transformKeys
  name_en?: string
  nameEn?: string        // camelCase alias after transformKeys
  description_es?: string
  descriptionEs?: string // camelCase alias after transformKeys
  description_fr?: string
  descriptionFr?: string // camelCase alias after transformKeys
  description_en?: string
  descriptionEn?: string // camelCase alias after transformKeys
  display_order?: number
  displayOrder?: number  // camelCase alias after transformKeys
  icon?: string
  color?: string
  is_active: boolean
  isActive?: boolean     // camelCase alias after transformKeys
  created_at: string
  createdAt?: string     // camelCase alias after transformKeys
  updated_at?: string
  updatedAt?: string     // camelCase alias after transformKeys
}

// =============================================================================
// FISCAL SERVICE INTERFACES
// =============================================================================

export interface RateTier {
  minValue: number
  maxValue?: number  // null = unlimited
  rate: number
  fixedAmount?: number
}

export interface FiscalServiceBase {
  // Core identification
  serviceCode: string
  categoryId: number

  // Naming (Spanish source)
  nameEs: string
  descriptionEs?: string

  // Classification
  serviceType: ServiceTypeEnum
  calculationMethod: CalculationMethodEnum

  // Fixed amounts
  tasaExpedicion?: number
  tasaRenovacion?: number
  expeditionFormula?: string
  expeditionUnitMeasure?: string
  renewalFormula?: string
  renewalUnitMeasure?: string

  // Variable calculation
  basePercentage?: number
  percentageOf?: string
  unitRate?: number
  unitType?: string
  calculationConfig?: Record<string, any>
  rateTiers?: RateTier[]

  // Validity
  validityPeriodMonths?: number
  renewalFrequencyMonths?: number
  gracePeriodDays?: number
  latePenaltyPercentage?: number
  latePenaltyFixed?: number
  penaltyCalculationRules?: Record<string, any>

  // Hierarchical
  parentServiceId?: number
  tierGroupName?: string
  isTierComponent?: boolean

  // Eligibility
  eligibilityCriteria?: Record<string, any>
  exemptionConditions?: any[]

  // Legal
  legalReference?: string
  regulatoryArticles?: string[]
  tariffEffectiveFrom: string
  tariffEffectiveTo?: string

  // Status and metadata
  status: ServiceStatusEnum
  priority?: number
  complexityLevel?: number
  processingTimeDays?: number

  // Description visibility (admin toggle)
  descriptionVisible?: boolean
}

export interface FiscalServiceCreate extends FiscalServiceBase {}

export interface FiscalServiceUpdate {
  categoryId?: number
  nameEs?: string
  descriptionEs?: string
  serviceType?: ServiceTypeEnum
  calculationMethod?: CalculationMethodEnum
  tasaExpedicion?: number
  tasaRenovacion?: number
  expeditionFormula?: string
  expeditionUnitMeasure?: string
  renewalFormula?: string
  renewalUnitMeasure?: string
  basePercentage?: number
  percentageOf?: string
  unitRate?: number
  unitType?: string
  calculationConfig?: Record<string, any>
  rateTiers?: RateTier[]
  validityPeriodMonths?: number
  renewalFrequencyMonths?: number
  gracePeriodDays?: number
  latePenaltyPercentage?: number
  latePenaltyFixed?: number
  penaltyCalculationRules?: Record<string, any>
  parentServiceId?: number
  tierGroupName?: string
  isTierComponent?: boolean
  eligibilityCriteria?: Record<string, any>
  exemptionConditions?: any[]
  legalReference?: string
  regulatoryArticles?: string[]
  tariffEffectiveFrom?: string
  tariffEffectiveTo?: string
  status?: ServiceStatusEnum
  priority?: number
  complexityLevel?: number
  processingTimeDays?: number
  descriptionVisible?: boolean
}

export interface FiscalServiceResponse extends FiscalServiceBase {
  id: number
  viewCount: number
  calculationCount: number
  paymentCount: number
  favoriteCount: number
  createdAt: string
  updatedAt: string
  createdBy?: string
  updatedBy?: string
  // Hierarchy names from backend JOIN
  categoryName?: string
  sectorName?: string
  ministryName?: string
  // Enrichment metadata
  descriptionSource?: string
}

export interface FiscalServiceWithCategory extends FiscalServiceResponse {
  category?: Category
}

// =============================================================================
// DOCUMENT TEMPLATE INTERFACES
// =============================================================================

export interface DocumentTemplate {
  id: number
  templateCode: string
  documentNameEs: string
  descriptionEs?: string
  category?: string
  validityDurationMonths?: number
  validityNotes?: string
  usageCount: number
  isActive: boolean
  createdAt: string
  updatedAt?: string
  createdBy?: number
}

export interface DocumentTemplateCreate {
  templateCode: string
  documentNameEs: string
  descriptionEs?: string
  category?: string
  validityDurationMonths?: number
  validityNotes?: string
  isActive?: boolean
}

export interface DocumentTemplateUpdate {
  documentNameEs?: string
  descriptionEs?: string
  category?: string
  validityDurationMonths?: number
  validityNotes?: string
  isActive?: boolean
}

export interface ServiceDocumentAssignment {
  id: number
  fiscalServiceId: number
  documentTemplateId: number
  isRequiredExpedition: boolean
  isRequiredRenewal: boolean
  displayOrder: number
  customNotes?: string
  assignedAt: string
  assignedBy?: number
  // Populated by joins in repository
  documentName?: string
  serviceName?: string
}

// =============================================================================
// PROCEDURE TEMPLATE INTERFACES
// =============================================================================

export interface ProcedureTemplate {
  id: number
  templateCode: string
  nameEs: string
  descriptionEs?: string
  category?: string
  usageCount: number
  isActive: boolean
  createdAt: string
  updatedAt?: string
  createdBy?: number
}

export interface ProcedureTemplateCreate {
  templateCode: string
  nameEs: string
  descriptionEs?: string
  category?: string
  isActive?: boolean
}

export interface ProcedureTemplateUpdate {
  nameEs?: string
  descriptionEs?: string
  category?: string
  isActive?: boolean
}

export interface ProcedureStep {
  id: number
  templateId: number
  stepNumber: number
  descriptionEs: string
  instructionsEs?: string
  estimatedDurationMinutes?: number
  locationAddress?: string
  officeHours?: string
  requiresAppointment: boolean
  isOptional: boolean
  createdAt: string
  updatedAt?: string
}

export interface ProcedureStepCreate {
  templateId: number
  stepNumber: number
  descriptionEs: string
  instructionsEs?: string
  estimatedDurationMinutes?: number
  locationAddress?: string
  officeHours?: string
  requiresAppointment?: boolean
  isOptional?: boolean
}

export interface ProcedureStepUpdate {
  stepNumber?: number
  descriptionEs?: string
  instructionsEs?: string
  estimatedDurationMinutes?: number
  locationAddress?: string
  officeHours?: string
  requiresAppointment?: boolean
  isOptional?: boolean
}

export interface ServiceProcedureAssignment {
  id: number
  fiscalServiceId: number
  templateId: number
  appliesTo?: string  // "expedition" | "renewal" | "both"
  displayOrder: number
  customNotes?: string
  overrideSteps?: Record<string, any>
  assignedAt: string
  assignedBy?: number
  // Populated by joins in repository
  procedureName?: string
  serviceName?: string
}

// =============================================================================
// KEYWORD & TRANSLATION INTERFACES
// =============================================================================

export interface ServiceKeyword {
  id: number
  fiscalServiceId: number
  keyword: string
  languageCode: string  // "es" | "fr" | "en"
  weight: number  // 1-10
  isAutoGenerated: boolean
  createdAt: string
}

export interface EntityTranslation {
  entityType: TranslatableEntityType
  entityCode: string
  languageCode: string  // "fr" | "en" | "pt"
  fieldName: string  // "name" | "description" | etc
  translationText: string
  translationSource: string  // "manual" | "google_translate" | "deepl" | "chatgpt"
  translationQuality?: number  // 0-1
  createdAt: string
  updatedAt?: string
}

// =============================================================================
// CALCULATION INTERFACES
// =============================================================================

export interface CalculationInput {
  fiscalServiceId: number
  isRenewal: boolean
  baseValue?: number  // For percentage_based
  quantity?: number  // For unit_based
  totalAmount?: number  // For tiered_rates
  variables?: Record<string, any>  // For formula_based
}

export interface CalculationBreakdown {
  method: CalculationMethodEnum
  isRenewal: boolean
  baseFee?: number
  variableAmount?: number
  tiersApplied?: Array<Record<string, any>>
  formulaUsed?: string
  subtotal: number
  additionalFees?: Record<string, number>
  total: number
}

export interface CalculationResult {
  fiscalServiceId: number
  serviceCode: string
  serviceName: string
  calculationMethod: CalculationMethodEnum
  breakdown: CalculationBreakdown
  amountGnf: number
  currency: string
  calculatedAt: string
}

// =============================================================================
// SEARCH & FILTER INTERFACES
// =============================================================================

export interface FiscalServiceFilter {
  query?: string
  ministryId?: number
  sectorId?: number
  categoryId?: number
  serviceType?: ServiceTypeEnum
  calculationMethod?: CalculationMethodEnum
  status?: ServiceStatusEnum
  isActive?: boolean
  requiresDocuments?: boolean
  requiresProcedure?: boolean
}

// =============================================================================
// STATISTICS INTERFACE
// =============================================================================

export interface FiscalServiceStats {
  totalServices: number
  activeServices: number
  inactiveServices: number
  servicesByType: Record<string, number>
  servicesByCategory: Record<string, number>
  servicesByMinistry: Record<string, number>
  servicesByStatus: Record<string, number>
  averageProcessingTime: number
  mostUsedServices: Array<Record<string, any>>
  totalCalculations: number
  totalViews: number
}

// =============================================================================
// PAGINATED RESPONSE
// =============================================================================

export interface FiscalServiceListResponse {
  services: FiscalServiceResponse[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Convert snake_case to camelCase
 */
export function toCamelCase(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(v => toCamelCase(v))
  } else if (obj !== null && obj.constructor === Object) {
    return Object.keys(obj).reduce((result, key) => {
      const camelKey = key.replace(/_([a-z])/g, (g) => g[1].toUpperCase())
      result[camelKey] = toCamelCase(obj[key])
      return result
    }, {} as any)
  }
  return obj
}

/**
 * Convert camelCase to snake_case
 */
export function toSnakeCase(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(v => toSnakeCase(v))
  } else if (obj !== null && obj.constructor === Object) {
    return Object.keys(obj).reduce((result, key) => {
      const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase()
      result[snakeKey] = toSnakeCase(obj[key])
      return result
    }, {} as any)
  }
  return obj
}

/**
 * Type guard: Check if service is active
 */
export function isActiveService(service: FiscalServiceResponse): boolean {
  return service.status === ServiceStatusEnum.ACTIVE
}

/**
 * Type guard: Check if service requires documents
 */
export function requiresDocuments(service: FiscalServiceResponse & { requiredDocuments?: unknown[] }): boolean {
  return Array.isArray(service.requiredDocuments) && service.requiredDocuments.length > 0
}

// =============================================================================
// LOCALIZATION HELPERS
// =============================================================================

type LocalizableEntity = Ministry | Sector | Category

/**
 * Get localized name for an entity based on locale
 * Falls back to Spanish (name_es/nameEs) if translation not available
 * Supports both snake_case (backend) and camelCase (transformed) formats
 */
export function getLocalizedName(entity: LocalizableEntity, locale: string): string {
  // Check French - both camelCase and snake_case
  if (locale === 'fr' && (entity.nameFr || entity.name_fr)) {
    return entity.nameFr || entity.name_fr || ''
  }
  // Check English - both camelCase and snake_case
  if (locale === 'en' && (entity.nameEn || entity.name_en)) {
    return entity.nameEn || entity.name_en || ''
  }
  // Default to Spanish - both camelCase and snake_case
  return entity.nameEs || entity.name_es || ''
}

/**
 * Get localized description for an entity based on locale
 * Falls back to Spanish (description_es/descriptionEs) if translation not available
 * Supports both snake_case (backend) and camelCase (transformed) formats
 */
export function getLocalizedDescription(entity: LocalizableEntity, locale: string): string | undefined {
  // Check French - both camelCase and snake_case
  if (locale === 'fr' && (entity.descriptionFr || entity.description_fr)) {
    return entity.descriptionFr || entity.description_fr
  }
  // Check English - both camelCase and snake_case
  if (locale === 'en' && (entity.descriptionEn || entity.description_en)) {
    return entity.descriptionEn || entity.description_en
  }
  // Default to Spanish - both camelCase and snake_case
  return entity.descriptionEs || entity.description_es
}
