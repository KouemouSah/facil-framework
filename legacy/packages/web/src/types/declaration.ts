/**
 * Declaration Types - Aligned with Backend Pydantic Models
 *
 * Source: packages/backend/app/modules/declarations/models/declaration.py
 *
 * IMPORTANT: These types mirror the backend Pydantic schemas exactly
 * - Field names use camelCase (converted from snake_case in API layer)
 * - All enums match backend exactly
 * - Optional fields match backend optionality
 */

/**
 * Declaration Status Enum
 * Source: DATABASE_SCHEMA_REFERENCE.md declaration_status_enum
 */
export enum DeclarationStatus {
  DRAFT = 'draft',              // En cours de rédaction
  SUBMITTED = 'submitted',      // Soumise (envoyée)
  PROCESSING = 'processing',    // En traitement par agent
  ACCEPTED = 'accepted',        // Acceptée/Approuvée
  REJECTED = 'rejected',        // Rejetée
  AMENDED = 'amended',          // Amendée/Corrigée
}

/**
 * Declaration Type Enum (28 types)
 * Source: DATABASE_SCHEMA_REFERENCE.md declaration_type_enum
 *
 * Distribution:
 * - IVA: 90% volume (iva_destajo, iva_real)
 * - IRPF: 5% volume (income tax)
 * - Pétroliers: 4% volume, GROS MONTANTS (6 sous-types)
 * - Retenciones: 1% volume (3%, 5%, 10%)
 * - Autres: <1% volume (7 autres types)
 */
export enum DeclarationType {
  // IVA (Impuesto al Valor Agregado) - 90% volume
  IVA_DESTAJO = 'iva_destajo',                      // IVA au coup par coup
  IVA_REAL = 'iva_real',                            // IVA régime réel

  // IRPF (Impuesto sobre la Renta) - 5% volume
  INCOME_TAX = 'income_tax',                        // Impôt sur le revenu
  CORPORATE_TAX = 'corporate_tax',                  // Impôt sociétés

  // Pétroliers - 4% volume, GROS MONTANTS
  RETENCION_3PCT_PETROLERO = 'retencion_3pct_petrolero',
  RETENCION_5PCT_PETROLERO = 'retencion_5pct_petrolero',
  RETENCION_10PCT_PETROLERO = 'retencion_10pct_petrolero',
  PETROLEO_GAS = 'petroleo_gas',
  PETROLEO_DIESEL = 'petroleo_diesel',
  PETROLEO_ESSENCE = 'petroleo_essence',

  // Retenciones (Retenues à la source) - 1% volume
  RETENCION_3PCT = 'retencion_3pct',
  RETENCION_5PCT = 'retencion_5pct',
  RETENCION_10PCT = 'retencion_10pct',

  // Autres types (<1% volume)
  VAT_DECLARATION = 'vat_declaration',
  SALES_TAX = 'sales_tax',
  PROPERTY_TAX = 'property_tax',
  PAYROLL_TAX = 'payroll_tax',
  EXCISE_TAX = 'excise_tax',
  CUSTOMS_DECLARATION = 'customs_declaration',
  SPECIAL_TAX = 'special_tax',

  // Types additionnels
  QUARTERLY_RETURN = 'quarterly_return',
  ANNUAL_RETURN = 'annual_return',
  AMENDED_RETURN = 'amended_return',
  ESTIMATED_TAX = 'estimated_tax',
  WITHHOLDING_TAX = 'withholding_tax',
  CAPITAL_GAINS = 'capital_gains',
  INHERITANCE_TAX = 'inheritance_tax',
}

/**
 * Base Declaration Interface
 * Aligned with DeclarationBase Pydantic model
 */
export interface DeclarationBase {
  // Identifiers
  userId: string
  companyId?: string | null

  // Declaration metadata
  declarationType: DeclarationType
  fiscalYear: number
  fiscalPeriod?: string | null
  declarationDeadline: string // ISO date string

  // Financial data
  taxableBase?: number | null
  calculatedTax?: number | null
  deductions?: number | null
  credits?: number | null
  netTaxDue?: number | null

  // Status
  status: DeclarationStatus

  // Additional data (JSONB)
  declaredData: Record<string, any>
  supportingDocuments?: string[] | null

  // Notes
  taxpayerNotes?: string | null
  processorNotes?: string | null
  rejectionReason?: string | null

  // Digital signature
  digitalSignature?: string | null

  // Declaration nature
  declarationNature?: string | null
  originalDeclarationId?: string | null
}

/**
 * Declaration Create Input
 * Aligned with DeclarationCreate Pydantic model
 */
export interface DeclarationCreate extends Omit<DeclarationBase, 'userId' | 'status' | 'declaredData' | 'declarationDeadline'> {
  // userId is set from auth token, not input
  // status defaults to DRAFT
  // declaredData defaults to empty object

  userId?: never // Prevent setting userId from frontend
  status?: never // Prevent setting status on creation
  declaredData?: Record<string, any>

  // Make some fields optional for draft creation
  taxableBase?: number | null
  fiscalPeriod?: string | null
  declarationDeadline?: string | null // Can be calculated if not provided
}

/**
 * Declaration Update Input
 * Aligned with DeclarationUpdate Pydantic model
 */
export interface DeclarationUpdate {
  // Financial data (all optional for partial updates)
  taxableBase?: number | null
  calculatedTax?: number | null
  deductions?: number | null
  credits?: number | null
  netTaxDue?: number | null

  // Status updates
  status?: DeclarationStatus
  taxpayerNotes?: string | null
  processorNotes?: string | null
  rejectionReason?: string | null

  // Data updates
  declaredData?: Record<string, any>
  supportingDocuments?: string[] | null
}

/**
 * Declaration Response
 * Aligned with DeclarationResponse Pydantic model
 */
export interface DeclarationResponse extends DeclarationBase {
  // Database fields
  id: string
  declarationNumber: string
  createdAt: string // ISO datetime string
  updatedAt: string // ISO datetime string
  submittedAt?: string | null // ISO datetime string
  processedAt?: string | null // ISO datetime string

  // Processor info
  processedBy?: string | null

  // Signature
  signatureTimestamp?: string | null // ISO datetime string

  // Related entities (from joins)
  userEmail?: string | null
  companyName?: string | null
  processorName?: string | null
}

/**
 * Declaration List Response (Paginated)
 * Aligned with DeclarationListResponse Pydantic model
 */
export interface DeclarationListResponse {
  declarations: DeclarationResponse[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

/**
 * Workflow Stage
 */
export interface WorkflowStage {
  stage: string
  name: string
  completed: boolean
}

/**
 * Declaration Workflow Status
 * Aligned with DeclarationWorkflowStatus Pydantic model
 */
export interface DeclarationWorkflowStatus {
  declarationId: string
  currentStage: string
  stages: WorkflowStage[]
  nextActions: string[]

  // Additional context
  status: DeclarationStatus
  submittedAt?: string | null
  processedAt?: string | null
  processedBy?: string | null
}

/**
 * Declaration Search/Filter Params
 * Aligned with DeclarationSearchFilter Pydantic model
 */
export interface DeclarationSearchFilter {
  // User/Company filters
  userId?: string
  companyId?: string

  // Declaration filters
  status?: DeclarationStatus
  declarationType?: DeclarationType
  declarationNature?: string

  // Fiscal period filters
  fiscalYear?: number
  fiscalPeriod?: string

  // Date filters
  createdAfter?: string // ISO datetime
  createdBefore?: string // ISO datetime
  submittedAfter?: string // ISO datetime
  submittedBefore?: string // ISO datetime
  deadlineAfter?: string // ISO date
  deadlineBefore?: string // ISO date

  // Search
  declarationNumber?: string
  searchQuery?: string

  // Administrative filters
  processedBy?: string
}

/**
 * Declaration Statistics
 * Aligned with DeclarationStats Pydantic model
 */
export interface DeclarationStats {
  // Count metrics
  totalDeclarations: number
  byStatus: Record<string, number>
  byType: Record<string, number>

  // Performance metrics
  averageProcessingTimeHours: number
  completionRate: number

  // Financial metrics
  totalTaxCollected: number
  pendingTax: number

  // Time-based metrics
  declarationsThisMonth: number
  declarationsThisWeek: number

  // Popular types (top 5)
  popularTypes: Array<{
    type: string
    count: number
    label?: string
  }>
}

/**
 * Helper type guards
 */
export const isDeclarationStatus = (value: string): value is DeclarationStatus => {
  return Object.values(DeclarationStatus).includes(value as DeclarationStatus)
}

export const isDeclarationType = (value: string): value is DeclarationType => {
  return Object.values(DeclarationType).includes(value as DeclarationType)
}

/**
 * Type mapping helpers for API conversion
 * Backend uses snake_case, Frontend uses camelCase
 */
export const toSnakeCaseStr = (str: string): string => {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

export const toCamelCaseStr = (str: string): string => {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}
