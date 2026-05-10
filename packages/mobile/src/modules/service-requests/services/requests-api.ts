/**
 * Service Requests API
 */

import { apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  ServiceRequestListResponse,
  ServiceRequestFilters,
  DetailViewResponse,
  WorkflowInfo,
} from '../types/requests.types';

/** GET /service-requests/ with filters and pagination */
export async function getRequests(
  filters: ServiceRequestFilters,
): Promise<ServiceRequestListResponse> {
  const params: Record<string, unknown> = {
    page: filters.page,
    page_size: filters.page_size,
  };
  if (filters.status) params.status = filters.status;
  if (filters.workflow_code) params.workflow_code = filters.workflow_code;
  if (filters.category) params.category = filters.category;
  if (filters.search) params.search = filters.search;
  if (filters.date_from) params.date_from = filters.date_from;
  if (filters.date_to) params.date_to = filters.date_to;

  return apiGet<ServiceRequestListResponse>(
    API_ENDPOINTS.serviceRequests.list,
    params,
  );
}

/** GET /service-requests/{id}/detail-view */
export async function getRequestDetailView(
  id: string,
): Promise<DetailViewResponse> {
  return apiGet<DetailViewResponse>(
    API_ENDPOINTS.serviceRequests.detailView(id),
  );
}

/** GET /service-requests/workflows */
export async function getAvailableWorkflows(
  category?: string,
): Promise<WorkflowInfo[]> {
  const params = category ? { category } : undefined;
  return apiGet<WorkflowInfo[]>(
    API_ENDPOINTS.serviceRequests.workflows,
    params,
  );
}
