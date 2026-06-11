/**
 * Support Tickets API — thin wrappers around `/support/*` endpoints.
 */

import { apiGet, apiPost } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  MyTicketsFilters,
  SupportCategory,
  SupportMessage,
  SupportMessagePayload,
  SupportTicket,
  SupportTicketCreatePayload,
  SupportTicketListResponse,
} from '../types/support.types';

/** GET /support/tickets/my — paginated list of *my* tickets. */
export async function listMyTickets(
  filters: MyTicketsFilters & { page: number },
): Promise<SupportTicketListResponse> {
  const params: Record<string, unknown> = {
    page: filters.page,
    page_size: filters.page_size ?? 20,
  };
  if (filters.status) params.status = filters.status;
  return apiGet<SupportTicketListResponse>(API_ENDPOINTS.support.myTickets, params);
}

/** GET /support/tickets/{id} — detail with ownership check server-side. */
export async function getTicket(ticketId: number): Promise<SupportTicket> {
  return apiGet<SupportTicket>(API_ENDPOINTS.support.ticket(ticketId));
}

/**
 * GET /support/tickets/{id}/messages — chronological message thread.
 * The backend filters out `is_internal=true` rows for non-admin callers.
 */
export async function listTicketMessages(ticketId: number): Promise<SupportMessage[]> {
  return apiGet<SupportMessage[]>(API_ENDPOINTS.support.ticketMessages(ticketId));
}

/** POST /support/tickets — create a new ticket. */
export async function createTicket(payload: SupportTicketCreatePayload): Promise<SupportTicket> {
  return apiPost<SupportTicket>(API_ENDPOINTS.support.createTicket, payload);
}

/** POST /support/tickets/{id}/messages — append a citizen reply. */
export async function postMessage(
  ticketId: number,
  payload: SupportMessagePayload,
): Promise<SupportMessage> {
  return apiPost<SupportMessage>(
    API_ENDPOINTS.support.ticketMessages(ticketId),
    { ...payload, is_internal: false },
  );
}

/** POST /support/tickets/{id}/close — owner or admin can close. */
export async function closeTicket(ticketId: number): Promise<SupportTicket> {
  return apiPost<SupportTicket>(API_ENDPOINTS.support.closeTicket(ticketId));
}

/** GET /support/categories — list of categories the current user can pick from. */
export async function listCategories(activeOnly = true): Promise<SupportCategory[]> {
  return apiGet<SupportCategory[]>(API_ENDPOINTS.support.categories, {
    is_active: activeOnly,
  });
}
