/**
 * Fiscal Config Rules — Types for centralized configuration engine.
 * Mirrors backend Pydantic models in config_rules.py.
 *
 * Specificity-based resolution: item(50) > ministry(30) > fee_type(20) > bundle(10) > global(0).
 */

// ============================================================
// Enums
// ============================================================

export type ConfigType = 'penalty' | 'deadline' | 'installment' | 'processing_mode'

export const CONFIG_TYPE_LABELS: Record<ConfigType, { es: string; fr: string; en: string }> = {
  penalty: { es: 'Penalidad', fr: 'Pénalité', en: 'Penalty' },
  deadline: { es: 'Fecha límite', fr: 'Date limite', en: 'Deadline' },
  installment: { es: 'Cuotas', fr: 'Versements', en: 'Installment' },
  processing_mode: { es: 'Modo de proceso', fr: 'Mode de traitement', en: 'Processing Mode' },
}

export const SPECIFICITY_LABELS: Record<string, { es: string; fr: string; en: string }> = {
  '0': { es: 'Global', fr: 'Global', en: 'Global' },
  '10': { es: 'Bundle', fr: 'Bundle', en: 'Bundle' },
  '20': { es: 'Tipo de tasa', fr: 'Type de taxe', en: 'Fee Type' },
  '30': { es: 'Ministerio', fr: 'Ministère', en: 'Ministry' },
  '50': { es: 'Ítem', fr: 'Article', en: 'Item' },
}

// ============================================================
// Config JSON shapes (discriminated by configType)
// ============================================================

export interface PenaltyConfig {
  rate: number
  grace_days?: number
  max_rate?: number
  type?: 'percentage' | 'flat'
}

export interface DeadlineConfig {
  month: number
  day: number
  type?: string
  grace_days?: number
}

export interface InstallmentConfig {
  max_installments: number
  frequency?: 'monthly' | 'bi-monthly' | 'quarterly'
  min_amount?: number
}

export interface ProcessingModeConfig {
  mode: 'per_line' | 'consolidated'
}

export type ConfigPayload = PenaltyConfig | DeadlineConfig | InstallmentConfig | ProcessingModeConfig

// ============================================================
// Response interfaces
// ============================================================

export interface ConfigRuleResponse {
  id: string
  configType: ConfigType
  bundleId: string | null
  feeType: string | null
  ministryId: number | null
  itemId: string | null
  effectiveFrom: string
  effectiveTo: string | null
  isEnabled: boolean
  config: Record<string, unknown>
  specificity: number
  nameEs: string | null
  description: string | null
  createdBy: string | null
  updatedBy: string | null
  createdAt: string
  updatedAt: string

  // Enriched
  bundleName?: string | null
  ministryName?: string | null
}

export interface ConfigRuleListResponse {
  items: ConfigRuleResponse[]
  total: number
  page: number
  pageSize: number
}

export interface RecomputeResult {
  affectedItems: number
  bundleId: string | null
}

// ============================================================
// Request interfaces
// ============================================================

export interface ConfigRuleCreateInput {
  configType: ConfigType
  bundleId?: string
  feeType?: string
  ministryId?: number
  itemId?: string
  effectiveFrom?: string
  effectiveTo?: string
  isEnabled?: boolean
  config: Record<string, unknown>
  nameEs?: string
  description?: string
}

export interface ConfigRuleUpdateInput {
  effectiveFrom?: string
  effectiveTo?: string
  isEnabled?: boolean
  config?: Record<string, unknown>
  nameEs?: string
  description?: string
}
