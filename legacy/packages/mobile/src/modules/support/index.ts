/**
 * Public surface of the support feature module.
 */

export * from './types/support.types';
export * as supportApi from './services/support-api';
export {
  SUPPORT_QUERY_KEYS,
  useMyTickets,
  useTicket,
  useTicketMessages,
  useSupportCategories,
  useCreateTicket,
  usePostTicketMessage,
  useCloseTicket,
} from './services/support-hooks';
export { TicketListItem } from './components/ticket-list-item';
export { TicketStatusBadge } from './components/ticket-status-badge';
export { TicketPriorityBadge } from './components/ticket-priority-badge';
export { MessageBubble } from './components/message-bubble';
