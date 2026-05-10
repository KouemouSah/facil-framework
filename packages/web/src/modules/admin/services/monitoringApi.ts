import apiClient from '@/core/api/client'

// ============================================================================
// OPERATIONS CENTER TYPES
// ============================================================================

export interface PaymentEntityRow {
  entity_code: string
  pending_count: number
  pending_amount: number
  avg_wait_hours: number
  sla_violated_count: number
}

export interface OperationsDashboard {
  payments: {
    by_entity: PaymentEntityRow[]
    total_pending: number
    total_pending_amount: number
  }
  agents: {
    total_agents: number
    agents_available: number
    agents_overloaded: number
    agents_unavailable: number
    agents_inactive_48h: number
    avg_capacity: number
  }
  pipeline: {
    submitted: number
    under_review: number
    in_progress: number
    payment_phase: number
    paid: number
    active_escalations: number
    high_priority: number
    new_24h: number
    completed_24h: number
  }
  stale_locks: number
  pool: {
    max_size: number
    current_size: number
    free: number
    used: number
  } | null
  fetched_at: string
}

export interface IntegrationStatus {
  status: string
  type?: string
  enabled?: boolean
  response_ms?: number | null
}

export interface IntegrationsHealth {
  database: IntegrationStatus
  redis: IntegrationStatus
  bange: IntegrationStatus
  gemini: IntegrationStatus
  checked_at: string
}

export interface CronTriggerResult {
  job: string
  result: Record<string, unknown>
  triggered_by: string
  triggered_at: string
}

// ============================================================================
// API METHODS
// ============================================================================

export const monitoringApi = {
  async getOperationsDashboard() {
    const response = await apiClient.get<OperationsDashboard>(
      '/admin/monitoring/operations/dashboard'
    )
    return response.data
  },

  async getIntegrationsHealth() {
    const response = await apiClient.get<IntegrationsHealth>(
      '/admin/monitoring/operations/integrations'
    )
    return response.data
  },

  async triggerCronJob(jobName: string) {
    const response = await apiClient.post<CronTriggerResult>(
      `/admin/monitoring/operations/trigger/${jobName}`
    )
    return response.data
  },
}
