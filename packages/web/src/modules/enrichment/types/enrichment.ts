export interface EnrichmentStats {
  totalServices: number
  withDescription: number
  withDescriptionPct: number
  descManual: number
  descAiGenerated: number
  descAiDraft: number
  descAiApproved: number
  withKeywords: number
  withKeywordsPct: number
  withTranslationsFr: number
  withTranslationsEn: number
  queuePending: number
  queueProcessing: number
  queueCompleted: number
  queueFailed: number
  breakdown: Array<{ taskType: string; status: string; cnt: number }>
}

export interface EnrichmentTask {
  id: string
  fiscalServiceId: number
  taskType: string
  status: string
  tokensUsed: number | null
  outputData: Record<string, unknown> | null
  errorMessage: string | null
  attempts: number
  processedAt: string | null
  createdAt: string | null
  serviceCode: string | null
  nameEs: string | null
  ministryCode: string | null
  ministryName: string | null
}

export interface PendingDraft {
  id: number
  serviceCode: string | null
  nameEs: string
  descriptionEs: string | null
  descriptionSource: string | null
  categoryName: string | null
  ministryName: string | null
  updatedAt: string | null
}

export interface EnrichmentSeedResult {
  enqueuedDescriptions: number
  enqueuedTranslations: number
  enqueuedKeywords: number
  autoProcessing: boolean
}

export interface ReviewResponse {
  serviceId: number
  action: string
  previousSource: string | null
  newSource: string | null
}

export interface BulkVisibilityResult {
  affected: number
  visible: boolean
  filtersApplied: Record<string, unknown>
}

export interface MinistryOption {
  id: number
  nameEs: string
  serviceCount: number
}

export interface EnrichmentProgress {
  jobId: string | null
  total: number
  processed: number
  failed: number
  skipped: number
  tokensTotal: number
  status: 'idle' | 'running' | 'circuit_breaker_pause' | 'completed' | 'already_running'
}
