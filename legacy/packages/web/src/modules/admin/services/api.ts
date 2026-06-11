/**
 * Admin API Service
 * Handles admin system operations (diagnostics, migrations, system config)
 *
 * @module admin/services
 * @author Claude Code
 * @date 2025-11-26
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/admin (from app/modules/admin/api/admin_routes.py)
 * - GET  /api/v1/admin/diagnostic/secrets  → check_secrets
 * - POST /api/v1/admin/migrate/grandfather-users → grandfather_migration
 *
 * NOTE: User management routes are in users-admin module
 */

import { fetchClient } from '@/core/api';
import type {
  SecretsCheckResponse,
  MigrationResult,
  SystemDiagnostics,
  SystemMetrics,
} from '../types';

// =============================================================================
// CONFIGURATION
// =============================================================================

const ADMIN_BASE = '/admin';

// =============================================================================
// ADMIN API
// =============================================================================

export const adminApi = {
  // ===========================================================================
  // DIAGNOSTICS
  // ===========================================================================

  /**
   * Check secrets configuration (SMTP, API keys, etc.)
   * BACKEND: GET /api/v1/admin/diagnostic/secrets
   * ROUTE: check_secrets() in admin_routes.py
   * PERMISSION: admin.view_diagnostics
   */
  checkSecrets: async (): Promise<SecretsCheckResponse> => {
    return fetchClient.get<SecretsCheckResponse>(`${ADMIN_BASE}/diagnostic/secrets`);
  },

  /**
   * Get system diagnostics
   * BACKEND: GET /api/v1/admin/diagnostic/system
   * PERMISSION: admin.view_diagnostics
   */
  getSystemDiagnostics: async (): Promise<SystemDiagnostics> => {
    return fetchClient.get<SystemDiagnostics>(`${ADMIN_BASE}/diagnostic/system`);
  },

  /**
   * Get system metrics
   * BACKEND: GET /api/v1/admin/diagnostic/metrics
   * PERMISSION: admin.view_diagnostics
   */
  getSystemMetrics: async (): Promise<SystemMetrics> => {
    return fetchClient.get<SystemMetrics>(`${ADMIN_BASE}/diagnostic/metrics`);
  },

  // ===========================================================================
  // MIGRATIONS
  // ===========================================================================

  /**
   * Run grandfather users migration
   * Marks existing users as email_verified (Migration 002)
   * BACKEND: POST /api/v1/admin/migrate/grandfather-users
   * ROUTE: grandfather_migration() in admin_routes.py
   * PERMISSION: admin.run_migrations
   */
  runGrandfatherMigration: async (): Promise<MigrationResult> => {
    return fetchClient.post<MigrationResult>(`${ADMIN_BASE}/migrate/grandfather-users`);
  },

  // ===========================================================================
  // HEALTH CHECK
  // ===========================================================================

  /**
   * Simple health check
   * BACKEND: GET /api/v1/admin/health
   */
  healthCheck: async (): Promise<{ status: string; timestamp: string }> => {
    return fetchClient.get(`${ADMIN_BASE}/health`);
  },
};

// =============================================================================
// EXPORTS
// =============================================================================

export default adminApi;
