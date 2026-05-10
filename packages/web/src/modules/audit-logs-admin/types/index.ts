/**
 * Audit Logs Admin Types
 * Aligned with backend AuditLogResponse (admin.py:182)
 */

export interface AuditLog {
  id: string
  user_id: string | null
  entity_type: string
  entity_id: string
  action: string
  old_values?: Record<string, unknown> | null
  new_values?: Record<string, unknown> | null
  ip_address?: string | null
  user_agent?: string | null
  created_at: string
}

export interface PaginatedAuditLogsResponse {
  items: AuditLog[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface AuditLogStats {
  total_logs: number
  by_action: Record<string, number>
  by_entity_type: Record<string, number>
}

// Keep for backward compatibility — used in filters
export type AuditAction = string

export interface GeminiUsageStats {
  total_calls: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  estimated_cost_usd: number
  error_count: number
  fallback_count: number
  avg_processing_time_ms: number
  avg_confidence: number
  daily_breakdown: Array<{
    day: string
    calls: number
    tokens: number
    errors: number
  }>
  by_workflow: Array<{
    workflow: string
    calls: number
    tokens: number
  }>
  by_document_category: Array<{
    category: string
    calls: number
    tokens: number
    avg_confidence: number
  }>
}
