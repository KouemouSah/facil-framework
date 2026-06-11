/**
 * useEntityServiceRequests Hook
 * Fetches and manages service requests for an entity
 *
 * @module agent-dashboard/hooks/useEntityServiceRequests
 * @date 2026-01-25
 */

import { useQuery } from '@tanstack/react-query';
import {
  agentRequestsApi,
  ServiceRequestFilters,
  ServiceRequestListResponse,
  ActionType,
} from '../services/agent-requests-api';

export interface UseEntityServiceRequestsOptions {
  entityCode: string;
  action?: ActionType;
  status?: string;
  workflowCode?: string;
  solicitudType?: 'expedicion' | 'renovacion';
  motivo?: 'vencimiento' | 'perdida' | 'robo' | 'deterioro';
  search?: string;
  priority?: 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';
  agentId?: string;
  page?: number;
  pageSize?: number;
  enabled?: boolean;
}

export function useEntityServiceRequests(options: UseEntityServiceRequestsOptions) {
  const {
    entityCode,
    action = 'pending',
    status,
    workflowCode,
    solicitudType,
    motivo,
    search,
    priority,
    agentId,
    page = 1,
    pageSize = 20,
    enabled = true,
  } = options;

  const filters: ServiceRequestFilters = {
    action,
    status,
    workflowCode,
    solicitudType,
    motivo,
    search,
    priority,
    agentId,
    page,
    pageSize,
  };

  const query = useQuery<ServiceRequestListResponse, Error>({
    queryKey: ['entity-service-requests', entityCode, filters],
    queryFn: () => agentRequestsApi.getEntityRequests(entityCode, filters),
    enabled: enabled && !!entityCode,
    staleTime: 30 * 1000, // 30 seconds
    refetchOnWindowFocus: true,
  });

  return {
    ...query,
    requests: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    totalPages: query.data?.totalPages ?? 1,
    currentPage: query.data?.page ?? page,
  };
}

// Re-export types
export type { ActionType, ServiceRequestListItem, ServiceRequestFilters } from '../services/agent-requests-api';
