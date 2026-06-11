/**
 * Support React Query hooks.
 */

import {
  useMutation,
  useQuery,
  useInfiniteQuery,
  useQueryClient,
} from '@tanstack/react-query';

import * as supportApi from './support-api';
import type {
  MyTicketsFilters,
  SupportMessagePayload,
  SupportTicket,
  SupportTicketCreatePayload,
} from '../types/support.types';

export const SUPPORT_QUERY_KEYS = {
  myTickets: (filters: Omit<MyTicketsFilters, never> | undefined = {}) =>
    ['support', 'my-tickets', filters] as const,
  ticket: (id: number) => ['support', 'ticket', id] as const,
  ticketMessages: (id: number) => ['support', 'ticket', id, 'messages'] as const,
  categories: ['support', 'categories'] as const,
} as const;

const DEFAULT_PAGE_SIZE = 20;

export function useMyTickets(filters: MyTicketsFilters = {}) {
  return useInfiniteQuery({
    queryKey: SUPPORT_QUERY_KEYS.myTickets(filters),
    queryFn: ({ pageParam = 1 }) =>
      supportApi.listMyTickets({
        page: pageParam as number,
        page_size: filters.page_size ?? DEFAULT_PAGE_SIZE,
        status: filters.status,
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
    staleTime: 30_000,
  });
}

export function useTicket(ticketId: number | null | undefined, enabled = true) {
  return useQuery({
    queryKey: SUPPORT_QUERY_KEYS.ticket((ticketId as number) ?? 0),
    queryFn: () => supportApi.getTicket(ticketId as number),
    enabled: enabled && !!ticketId,
    staleTime: 15_000,
  });
}

export function useTicketMessages(ticketId: number | null | undefined, enabled = true) {
  return useQuery({
    queryKey: SUPPORT_QUERY_KEYS.ticketMessages((ticketId as number) ?? 0),
    queryFn: () => supportApi.listTicketMessages(ticketId as number),
    enabled: enabled && !!ticketId,
    staleTime: 10_000,
  });
}

/** Categories rarely change — long staleTime. */
export function useSupportCategories() {
  return useQuery({
    queryKey: SUPPORT_QUERY_KEYS.categories,
    queryFn: () => supportApi.listCategories(true),
    staleTime: 60 * 60_000, // 1h
  });
}

export function useCreateTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SupportTicketCreatePayload) => supportApi.createTicket(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['support', 'my-tickets'] });
    },
  });
}

export function usePostTicketMessage(ticketId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SupportMessagePayload) =>
      supportApi.postMessage(ticketId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: SUPPORT_QUERY_KEYS.ticketMessages(ticketId),
      });
      queryClient.invalidateQueries({
        queryKey: SUPPORT_QUERY_KEYS.ticket(ticketId),
      });
    },
  });
}

/**
 * Close a ticket with **optimistic update** (P8.6) — the detail card flips
 * to "resolved" the moment the user taps the action, and rolls back to the
 * previous status if the backend rejects.
 */
export function useCloseTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ticketId: number) => supportApi.closeTicket(ticketId),

    onMutate: async (ticketId: number) => {
      const detailKey = SUPPORT_QUERY_KEYS.ticket(ticketId);
      // Pause refetches so the optimistic write isn't immediately overwritten.
      await queryClient.cancelQueries({ queryKey: detailKey });

      const previous = queryClient.getQueryData<SupportTicket>(detailKey);
      if (previous) {
        queryClient.setQueryData<SupportTicket>(detailKey, {
          ...previous,
          status: 'resolved',
          resolved_at: new Date().toISOString(),
        });
      }
      return { previous };
    },

    onError: (_err, ticketId, context) => {
      // Rollback the cached ticket if the backend rejects the close.
      if (context?.previous) {
        queryClient.setQueryData(SUPPORT_QUERY_KEYS.ticket(ticketId), context.previous);
      }
    },

    onSettled: (_data, _err, ticketId) => {
      // Re-sync once the dust has settled — covers both success (status may
      // have moved to "closed" rather than "resolved") and rollback paths.
      queryClient.invalidateQueries({ queryKey: SUPPORT_QUERY_KEYS.ticket(ticketId) });
      queryClient.invalidateQueries({ queryKey: ['support', 'my-tickets'] });
    },
  });
}
