/**
 * Bundle Workflow Types
 * Matches backend response shapes from BundleWorkflowService + BundleWorkflowRoutes.
 * All types use camelCase (transformed from backend snake_case via transformKeys).
 */

import type { FeeType, ProcessingMode } from '@/types/service-bundle'
import type { LicenseStatus, ObligationStatus } from '@/types/commercial-license'

// ── Wizard Steps ────────────────────────────────────────────────

export enum BundleStep {
  COMPANY_IDENTIFICATION = 0,
  DOCUMENT_UPLOAD = 1,
  CLASSIFICATION = 2,
  OBLIGATIONS_REVIEW = 3,
  PAYMENT = 4,
  CONFIRMATION = 5,
}

export const BUNDLE_STEP_LABELS: Record<BundleStep, { es: string; fr: string; en: string }> = {
  [BundleStep.COMPANY_IDENTIFICATION]: {
    es: 'Empresa',
    fr: 'Entreprise',
    en: 'Company',
  },
  [BundleStep.DOCUMENT_UPLOAD]: {
    es: 'Documentos',
    fr: 'Documents',
    en: 'Documents',
  },
  [BundleStep.CLASSIFICATION]: {
    es: 'Zona y Categoria',
    fr: 'Zone et Categorie',
    en: 'Zone & Category',
  },
  [BundleStep.OBLIGATIONS_REVIEW]: {
    es: 'Obligaciones',
    fr: 'Obligations',
    en: 'Obligations',
  },
  [BundleStep.PAYMENT]: {
    es: 'Pago',
    fr: 'Paiement',
    en: 'Payment',
  },
  [BundleStep.CONFIRMATION]: {
    es: 'Confirmacion',
    fr: 'Confirmation',
    en: 'Confirmation',
  },
}

// ── Company Types ───────────────────────────────────────────────

export interface CompanySummary {
  id: string
  legalName: string
  taxId: string
  nif: string | null
  registrationNumber: string | null
  commerceType: string | null
  regimenFiscal: string | null
  zoneCode: string | null
  cityName: string | null
  isVerified: boolean
}

export interface CompanySearchResult extends CompanySummary {
  registeredByCurrentUser: boolean
}

export interface MyCompanyWithStatus {
  company: CompanySummary
  licenseId: string | null
  licenseStatus: LicenseStatus | null
  pendingObligations: number
  fiscalYear: number
  isEligible: boolean
}

// ── Bundle / License Types ──────────────────────────────────────

export interface BundleSummary {
  id: string
  commerceType: string
  nameEs: string
}

export interface ObligationItem {
  id: string
  bundleItemId: string
  fiscalServiceName: string
  feeType: FeeType
  ministryName: string
  amount: number
  penaltyAmount: number
  total: number
  status: ObligationStatus
  isPayable: boolean
  dueDate: string | null
  paidAt: string | null
}

// ── Classification Preview Types ─────────────────────────────────

export interface ClassifyPreviewResponse {
  extractedData: {
    legalName: string | null
    registrationNumber: string | null
    nif: string | null
    formaJuridica: string | null
    localidad: string | null
    provincia: string | null
    sector: string | null
    objetoSocial: string | null
  }
  zoneResolved: boolean
  zone: { id: string; code: string; name: string; tier?: string } | null
  detectedTier: string | null
  detectedCity: string | null
  tierZones: Array<{ id: string; code: string; tier: string; rank: number; name: string; description: string }>
  availableZones: Array<{ id: string; code: string; tier: string; rank: number; name: string; description: string }>
  classification: {
    regimenFiscal: string | null
    commerceType: string | null
    confidence: number
  }
  availableCategories: Array<{ commerceType: string; bundleName: string }>
  availableCommerceTypes: Array<{ commerceType: string; bundleName: string }>
  needsManualZone: boolean
  needsManualCategory: boolean
}

// ── Request Types ───────────────────────────────────────────────

export interface BundleInitiateRequest {
  companyId: string
  fiscalYear?: number
}

export interface BundleInitiateFromUploadRequest {
  extraction: Record<string, unknown>
  fiscalYear?: number
  zoneId?: string
  commerceType?: string
}

export interface BundleValidateSelectionRequest {
  licenseId: string
  processingMode: ProcessingMode
  selectedObligationIds?: string[]
}

export interface BundleInitiatePaymentRequest {
  licenseId: string
  processingMode: ProcessingMode
  paymentMethod: string
  selectedObligationIds: string[]
  phoneNumber?: string
  wizardSessionId?: string
}

// ── Response Types ──────────────────────────────────────────────

export interface BundleInitiateResponse {
  licenseId: string
  alreadyComplete: boolean
  licenseStatus: LicenseStatus
  totalAmount: number
  amountPaid: number
  amountRemaining: number
  obligations: ObligationItem[]
  company: CompanySummary
  bundle: BundleSummary
  fiscalYear: number
  currency: string
  processingModesAvailable: ProcessingMode[]
  companyCreated?: boolean
  companyAlreadyExisted?: boolean
}

export interface BundleValidateSelectionResponse {
  valid: boolean
  processingMode: ProcessingMode
  selectedCount: number
  totalAmount: number
  selectedObligationIds: string[]
  currency: string
}

export interface BundlePaymentResult {
  success: boolean
  serviceRequestId: string
  paymentId: string
  paymentReference: string
  redirectUrl: string | null
  requiresAction: boolean
  actionType: string | null
  totalAmount: number
  obligationsCount: number
  processingMode: ProcessingMode
  messageEs: string
  messageFr: string
  messageEn: string
}

export interface MyCompaniesResponse {
  companies: MyCompanyWithStatus[]
}

export interface SearchCompanyResponse {
  companies: CompanySearchResult[]
  total: number
}
