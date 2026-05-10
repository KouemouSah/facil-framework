/**
 * Commercial Licenses — Types for OMS (Obligation Management System).
 * Mirrors backend Pydantic models in licenses.py.
 */

import type { FeeType } from './service-bundle'

// ============================================================
// Enums (union types)
// ============================================================

export type LicenseStatus = 'open' | 'partial' | 'complete' | 'overdue' | 'suspended' | 'closed'

export type ObligationStatus =
  | 'pending'
  | 'selected'
  | 'payment_pending'
  | 'paid'
  | 'processing'
  | 'completed'
  | 'overdue'
  | 'waived'
  | 'cancelled'

export type ComplianceEventType =
  | 'license_created'
  | 'obligation_created'
  | 'payment_initiated'
  | 'payment_validated'
  | 'obligation_routed'
  | 'agent_approved'
  | 'agent_rejected'
  | 'document_issued'
  | 'obligation_completed'
  | 'overdue_flagged'
  | 'penalty_applied'
  | 'reminder_sent'
  | 'license_completed'
  | 'license_renewed'
  | 'license_suspended'
  | 'config_changed'
  | 'waived'

export type ProcessingMode = 'per_line' | 'consolidated'

// ============================================================
// Label maps
// ============================================================

export const LICENSE_STATUS_LABELS: Record<LicenseStatus, { es: string; fr: string; en: string }> = {
  open: { es: 'Abierta', fr: 'Ouverte', en: 'Open' },
  partial: { es: 'Parcial', fr: 'Partiel', en: 'Partial' },
  complete: { es: 'Completa', fr: 'Complète', en: 'Complete' },
  overdue: { es: 'Vencida', fr: 'En retard', en: 'Overdue' },
  suspended: { es: 'Suspendida', fr: 'Suspendue', en: 'Suspended' },
  closed: { es: 'Cerrada', fr: 'Fermée', en: 'Closed' },
}

export const OBLIGATION_STATUS_LABELS: Record<ObligationStatus, { es: string; fr: string; en: string }> = {
  pending: { es: 'Pendiente', fr: 'En attente', en: 'Pending' },
  selected: { es: 'Seleccionada', fr: 'Sélectionnée', en: 'Selected' },
  payment_pending: { es: 'Pago pendiente', fr: 'Paiement en attente', en: 'Payment Pending' },
  paid: { es: 'Pagada', fr: 'Payée', en: 'Paid' },
  processing: { es: 'En proceso', fr: 'En traitement', en: 'Processing' },
  completed: { es: 'Completada', fr: 'Terminée', en: 'Completed' },
  overdue: { es: 'Vencida', fr: 'En retard', en: 'Overdue' },
  waived: { es: 'Exonerada', fr: 'Exonérée', en: 'Waived' },
  cancelled: { es: 'Cancelada', fr: 'Annulée', en: 'Cancelled' },
}

// ============================================================
// Response interfaces
// ============================================================

export interface LicenseResponse {
  id: string
  companyId: string
  serviceRequestId?: string | null
  bundleId: string
  zoneId: string
  cityId?: string | null
  fiscalYear: number
  processingMode: ProcessingMode

  totalAmount: string | number
  amountPaid: string | number
  penaltyAmount: string | number

  obligationsTotal: number
  obligationsPaid: number
  obligationsOverdue: number
  complianceScore: string | number | null

  status: LicenseStatus
  deadline: string | null
  openedAt: string
  completedAt: string | null
  closedAt: string | null

  createdBy: string | null
  createdAt: string
  updatedAt: string

  // Enriched (from JOINs)
  companyName?: string | null
  bundleName?: string | null
  zoneCode?: string | null
}

export interface LicenseSummary {
  id: string
  companyId: string
  fiscalYear: number
  status: LicenseStatus
  totalAmount: string | number
  amountPaid: string | number
  complianceScore: string | number | null
  obligationsTotal: number
  obligationsPaid: number
  deadline: string | null

  // Enriched
  companyName?: string | null
  bundleName?: string | null
  zoneCode?: string | null
}

export interface LicenseListResponse {
  items: LicenseSummary[]
  total: number
  page: number
  pageSize: number
}

export interface ObligationResponse {
  id: string
  licenseId: string
  bundleItemId: string
  fiscalServiceId: number
  ministryId: number | null
  feeType: FeeType

  amount: string | number
  penaltyAmount: string | number
  dueDate: string | null

  penaltyConfig: Record<string, unknown> | null
  deadlineConfig: Record<string, unknown> | null

  status: ObligationStatus
  paymentId: string | null
  paidAt: string | null

  userDocumentId: string | null
  issuedDocumentId: string | null

  previousYearPaid: boolean | null
  previousYearCheckedAt: string | null

  createdAt: string
  updatedAt: string

  // Enriched
  serviceName?: string | null
  serviceCode?: string | null
  ministryName?: string | null
}

export interface ObligationListResponse {
  items: ObligationResponse[]
  total: number
  page: number
  pageSize: number
}

export interface ComplianceEventResponse {
  id: string
  licenseId: string
  obligationId: string | null
  eventType: ComplianceEventType
  eventData: Record<string, unknown> | null
  triggeredBy: string | null
  createdAt: string
}

export interface ComplianceEventListResponse {
  items: ComplianceEventResponse[]
  total: number
  page: number
  pageSize: number
}

// ============================================================
// Request interfaces
// ============================================================

export interface LicenseCreateInput {
  companyId: string
  bundleId: string
  zoneId: string
  cityId?: string
  fiscalYear: number
  serviceRequestId?: string
}

export interface LicenseUpdateInput {
  status: LicenseStatus
}

export interface LicenseRenewInput {
  fiscalYear: number
}

export interface ObligationStatusUpdateInput {
  status: ObligationStatus
  paymentId?: string
  paidAt?: string
  userDocumentId?: string
  issuedDocumentId?: string
  penaltyAmount?: number
}

export interface BatchObligationUpdateInput {
  obligationIds: string[]
  status: ObligationStatus
  paymentId?: string
  paidAt?: string
}

// ============================================================
// Stats
// ============================================================

export interface LicenseStats {
  totalLicenses: number
  openLicenses: number
  partialLicenses: number
  completeLicenses: number
  overdueLicenses: number
  totalAmount: string | number
  amountPaid: string | number
  penaltyAmount: string | number
  avgComplianceScore: string | number
}
