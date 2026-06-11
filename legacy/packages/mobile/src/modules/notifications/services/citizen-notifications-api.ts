/**
 * Citizen notifications — server-side audit trail.
 *
 * Backend wiring:
 *   GET /service-requests/notifications
 *   -> { items, total, total_unread, page, page_size }
 *
 * Each item is built from `service_request_history` rows visible to the
 * citizen (RGPD-filtered: agent names hidden, only `performer_role` exposed).
 * Source: app/modules/service_requests/repositories/service_request_repository.py:1081
 *
 * The mobile inbox stores pushes locally (MMKV ring buffer). This endpoint is
 * the authoritative source — pulled at notification-screen mount + on refresh
 * — so a push that was missed (device offline, OS killed, permission denied)
 * still surfaces. Web parity: dashboard/notifications/page.tsx.
 */

import { apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';

/** Mirrors the shape produced by `get_citizen_notifications_paginated`. */
export interface ServerCitizenNotification {
  id: string;
  action: string;
  /** Humanized "<action> - <request_reference>" pre-built server-side. */
  title: string;
  message: string | null;
  performed_at: string;
  performer_role: 'agent' | 'system' | 'citizen';
  is_new: boolean;
  new_status: string | null;
  request_id: string;
}

export interface ServerCitizenNotificationsResponse {
  items: ServerCitizenNotification[];
  total: number;
  total_unread: number;
  page: number;
  page_size: number;
}

export interface ListCitizenNotificationsParams {
  page?: number;
  page_size?: number;
  /** Backend supports `payment | appointment | agent` shortcuts plus exact action codes. */
  action_filter?: string;
}

export async function listCitizenNotifications(
  params: ListCitizenNotificationsParams = {},
): Promise<ServerCitizenNotificationsResponse> {
  const query: Record<string, unknown> = {
    page: params.page ?? 1,
    page_size: params.page_size ?? 20,
  };
  if (params.action_filter) query.action_filter = params.action_filter;
  return apiGet<ServerCitizenNotificationsResponse>(
    API_ENDPOINTS.serviceRequests.notifications,
    query,
  );
}
