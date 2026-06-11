/**
 * Dashboard API Service
 */

import { apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type { DashboardSummary } from '../types/dashboard.types';

/** GET /service-requests/dashboard-summary */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiGet<DashboardSummary>(API_ENDPOINTS.serviceRequests.dashboardSummary);
}
