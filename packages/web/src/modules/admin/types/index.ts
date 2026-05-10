/**
 * Admin Module Types
 * Type definitions for admin operations (diagnostics, migrations, system)
 *
 * @module admin/types
 * @author Claude Code
 * @date 2025-11-26
 *
 * BACKEND ALIGNMENT:
 * - Schemas from: app/modules/admin/models/admin.py
 * - Routes from: app/modules/admin/api/admin_routes.py
 */

// =============================================================================
// DIAGNOSTICS
// =============================================================================

/**
 * System diagnostics response
 * BACKEND: SystemDiagnostics in admin.py
 */
export interface SystemDiagnostics {
  database_status: 'healthy' | 'degraded' | 'down';
  redis_status: 'healthy' | 'degraded' | 'down';
  storage_status: 'healthy' | 'degraded' | 'down';
  email_service_status: 'healthy' | 'degraded' | 'down';
  total_users: number;
  total_declarations: number;
  total_payments: number;
  system_version: string;
  environment: string;
  uptime_seconds: number;
}

/**
 * Secrets check response
 * BACKEND: GET /api/v1/admin/diagnostic/secrets
 */
export interface SecretsCheckResponse {
  success: boolean;
  secrets_status: Record<string, {
    configured: boolean;
    valid: boolean;
  }>;
  smtp_configuration: {
    host: string;
    port: number;
    use_tls: boolean;
    configured: boolean;
  };
  message: string;
}

// =============================================================================
// MIGRATIONS
// =============================================================================

/**
 * Migration result response
 * BACKEND: MigrationResult in admin.py
 */
export interface MigrationResult {
  success: boolean;
  migration_name: string;
  records_affected: number;
  message: string;
  errors: string[];
}

// =============================================================================
// SYSTEM METRICS
// =============================================================================

/**
 * System metrics for monitoring
 * BACKEND: SystemMetrics in admin.py
 */
export interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  active_connections: number;
  requests_per_minute: number;
  avg_response_time_ms: number;
  error_rate: number;
}

// =============================================================================
// SYSTEM CONFIGURATION
// =============================================================================

/**
 * System rule categories
 * BACKEND: SystemRuleCategory enum in admin.py
 */
export type SystemRuleCategory =
  | 'tax'
  | 'approval'
  | 'payment'
  | 'notification'
  | 'security'
  | 'workflow'
  | 'general';

/**
 * System rule value types
 * BACKEND: SystemRuleValueType enum in admin.py
 */
export type SystemRuleValueType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'json'
  | 'date'
  | 'percentage';

/**
 * System configuration rule
 * BACKEND: SystemRuleResponse in admin.py
 */
export interface SystemRule {
  id: string;
  rule_code: string;
  rule_category: SystemRuleCategory;
  name_es: string;
  name_fr?: string;
  name_en?: string;
  description?: string;
  rule_value: string;
  value_type: SystemRuleValueType;
  applies_to?: string[];
  effective_from?: string;
  effective_until?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * System config update request
 * BACKEND: SystemConfigUpdate in admin.py
 */
export interface SystemConfigUpdate {
  config_key: string;
  config_value: string;
  description?: string;
}
