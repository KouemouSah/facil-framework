/**
 * Support module types — aligned 1:1 with backend Pydantic models in
 * `packages/backend/app/modules/support/models/support.py`.
 *
 * BD-verified (live Supabase, 2026-04-27): the four `support_*` tables use
 * INTEGER primary keys, not UUIDs. JS preserves integer precision up to
 * `Number.MAX_SAFE_INTEGER` (~9e15), so a plain `number` is safe.
 */

/** Mirrors `TicketStatus` enum (support.py:22). */
export type TicketStatus =
  | 'open'
  | 'in_progress'
  | 'pending_user'
  | 'resolved'
  | 'closed';

/** Mirrors `TicketPriority` enum (support.py:14). */
export type TicketPriority = 'low' | 'normal' | 'high' | 'urgent';

/** Mirrors `TargetRole` enum (support.py:31). */
export type TargetRole = 'admin' | 'agent' | 'all';

/** Mirrors `SupportCategoryResponse` (support.py:94). */
export interface SupportCategory {
  id: number;
  code: string;
  name_es: string;
  name_fr: string | null;
  name_en: string | null;
  description_es: string | null;
  description_fr: string | null;
  description_en: string | null;
  target_role: TargetRole;
  icon: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
}

/** Mirrors `SupportTicketResponse` (support.py:145). */
export interface SupportTicket {
  id: number;
  ticket_number: string; // SUP-YYYYMMDD-XXXX
  category_id: number | null;
  category_name: string | null;
  subject: string;
  description: string;
  priority: TicketPriority;
  status: TicketStatus;
  created_by: string; // UUID
  created_by_name: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string | null;
  message_count: number;
}

/** Mirrors `SupportTicketListResponse` (support.py:190). */
export interface SupportTicketListResponse {
  tickets: SupportTicket[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** Mirrors `SupportMessageResponse` (support.py:228). */
export interface SupportMessage {
  id: number;
  ticket_id: number;
  sender_id: string; // UUID
  sender_name: string | null;
  sender_role: string | null;
  content: string;
  is_internal: boolean; // citizens only ever see is_internal=false; admins can post true
  created_at: string;
  attachments: SupportAttachment[];
}

/** Mirrors `SupportAttachmentResponse` (support.py:256). V1.1 — not exposed in current UI. */
export interface SupportAttachment {
  id: number;
  message_id: number;
  file_name: string;
  file_path: string;
  file_size: number | null;
  mime_type: string | null;
  created_at: string;
}

/** Body of `POST /support/tickets`. Mirrors `SupportTicketCreate` (support.py:118). */
export interface SupportTicketCreatePayload {
  category_id: number;
  /** 5-255 chars (backend validates min_length=5, max_length=255). */
  subject: string;
  /** Min 10 chars. */
  description: string;
  /** Default normal — citizens shouldn't pick `urgent` flippantly. */
  priority?: TicketPriority;
}

/** Body of `POST /support/tickets/{id}/messages`. Mirrors `SupportMessageCreate` (support.py:214). */
export interface SupportMessagePayload {
  content: string;
  /** Always false from a citizen client. */
  is_internal?: boolean;
}

/** Filters for `GET /support/tickets/my`. */
export interface MyTicketsFilters {
  status?: TicketStatus;
  page_size?: number;
}

/** Statuses considered "active" — used for the default chip filter. */
export const ACTIVE_TICKET_STATUSES: ReadonlySet<TicketStatus> = new Set([
  'open',
  'in_progress',
  'pending_user',
]);
