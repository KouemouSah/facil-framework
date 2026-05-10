/**
 * Agent Appointments Hooks
 * React Query hooks for appointments management
 *
 * @module agent-dashboard/hooks/useAppointments
 * @date 2026-01-26
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  agentAppointmentsApi,
  TodayAppointmentsListResponse,
  SlotsCalendarResponse,
  AgentBookingRequest,
  AgentBookingResponse,
  RescheduleRequest,
  RescheduleResponse,
  AppointmentDetail,
  AssignedRequestsListResponse,
} from '../services/appointments-api';
import type { EntityCode } from '../types';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const APPOINTMENTS_QUERY_KEYS = {
  today: (entityCode: string, locationId?: string) =>
    ['appointments', 'today', entityCode, locationId] as const,
  slotsDetailed: (entityCode: string, weekOffset: number, locationId?: string) =>
    ['appointments', 'slots-detailed', entityCode, weekOffset, locationId] as const,
  detail: (reservationId: string) =>
    ['appointments', 'detail', reservationId] as const,
  myAssigned: (entityCode: string, includeWithAppointment: boolean) =>
    ['appointments', 'my-assigned', entityCode, includeWithAppointment] as const,
};

// =============================================================================
// TODAY'S APPOINTMENTS HOOK
// =============================================================================

export interface UseTodayAppointmentsOptions {
  locationId?: string;
  enabled?: boolean;
}

export function useTodayAppointments(
  entityCode: EntityCode,
  options: UseTodayAppointmentsOptions = {}
) {
  const { locationId, enabled = true } = options;

  return useQuery<TodayAppointmentsListResponse, Error>({
    queryKey: APPOINTMENTS_QUERY_KEYS.today(entityCode, locationId),
    queryFn: () => agentAppointmentsApi.getTodayAppointments(entityCode, locationId),
    enabled: enabled && !!entityCode,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Refresh every minute
  });
}

// =============================================================================
// MY ASSIGNED REQUESTS HOOK (for appointment scheduling dropdown)
// =============================================================================

export interface UseMyAssignedRequestsOptions {
  includeWithAppointment?: boolean;
  enabled?: boolean;
}

export function useMyAssignedRequests(
  entityCode: EntityCode,
  options: UseMyAssignedRequestsOptions = {}
) {
  const { includeWithAppointment = true, enabled = true } = options;

  return useQuery<AssignedRequestsListResponse, Error>({
    queryKey: APPOINTMENTS_QUERY_KEYS.myAssigned(entityCode, includeWithAppointment),
    queryFn: () => agentAppointmentsApi.getMyAssignedRequests(entityCode, includeWithAppointment),
    enabled: enabled && !!entityCode,
    staleTime: 60 * 1000, // 1 minute
  });
}

// =============================================================================
// SLOTS CALENDAR HOOK
// =============================================================================

export interface UseSlotsDetailedOptions {
  weekOffset?: number;
  locationId?: string;
  enabled?: boolean;
}

export function useSlotsDetailed(
  entityCode: EntityCode,
  options: UseSlotsDetailedOptions = {}
) {
  const { weekOffset = 0, locationId, enabled = true } = options;

  return useQuery<SlotsCalendarResponse, Error>({
    queryKey: APPOINTMENTS_QUERY_KEYS.slotsDetailed(entityCode, weekOffset, locationId),
    queryFn: () => agentAppointmentsApi.getSlotsDetailed(entityCode, weekOffset, locationId),
    enabled: enabled && !!entityCode,
    staleTime: 30 * 1000, // 30 seconds
  });
}

// =============================================================================
// APPOINTMENT DETAIL HOOK
// =============================================================================

export function useAppointmentDetail(
  reservationId: string,
  enabled: boolean = true
) {
  return useQuery<AppointmentDetail, Error>({
    queryKey: APPOINTMENTS_QUERY_KEYS.detail(reservationId),
    queryFn: () => agentAppointmentsApi.getAppointmentDetail(reservationId),
    enabled: enabled && !!reservationId,
  });
}

// =============================================================================
// BOOKING MUTATION
// =============================================================================

export function useBookForCitizen() {
  const queryClient = useQueryClient();

  return useMutation<AgentBookingResponse, Error, AgentBookingRequest>({
    mutationFn: (booking) => agentAppointmentsApi.bookForCitizen(booking),
    onSuccess: (data) => {
      if (data.success) {
        // Invalidate relevant queries
        queryClient.invalidateQueries({ queryKey: ['appointments'] });
        queryClient.invalidateQueries({ queryKey: ['calendarSlots'] });
      }
    },
  });
}

// =============================================================================
// RESCHEDULE MUTATION
// =============================================================================

export interface RescheduleVariables {
  reservationId: string;
  data: RescheduleRequest;
}

export function useRescheduleAppointment() {
  const queryClient = useQueryClient();

  return useMutation<RescheduleResponse, Error, RescheduleVariables>({
    mutationFn: ({ reservationId, data }) =>
      agentAppointmentsApi.reschedule(reservationId, data),
    onSuccess: (data, variables) => {
      if (data.success) {
        // Invalidate relevant queries
        queryClient.invalidateQueries({ queryKey: ['appointments'] });
        queryClient.invalidateQueries({ queryKey: ['calendarSlots'] });
        queryClient.invalidateQueries({
          queryKey: APPOINTMENTS_QUERY_KEYS.detail(variables.reservationId),
        });
      }
    },
  });
}

// =============================================================================
// CANCEL MUTATION
// =============================================================================

export interface CancelVariables {
  reservationId: string;
  reason?: string;
}

export function useCancelAppointment() {
  const queryClient = useQueryClient();

  return useMutation<{ message: string }, Error, CancelVariables>({
    mutationFn: ({ reservationId, reason }) =>
      agentAppointmentsApi.cancelAppointment(reservationId, reason),
    onSuccess: () => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['calendarSlots'] });
    },
  });
}

// =============================================================================
// COMPLETE MUTATION
// =============================================================================

export function useCompleteAppointment() {
  const queryClient = useQueryClient();

  return useMutation<{ message: string }, Error, string>({
    mutationFn: (reservationId) =>
      agentAppointmentsApi.completeAppointment(reservationId),
    onSuccess: () => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
    },
  });
}

// =============================================================================
// EXPORTS
// =============================================================================

export type {
  TodayAppointmentsListResponse,
  SlotsCalendarResponse,
  AgentBookingRequest,
  AgentBookingResponse,
  RescheduleRequest,
  RescheduleResponse,
  AppointmentDetail,
  LocationInfo,
  TodayAppointmentDetail,
  DaySlotDetail,
  SlotTimeDetail,
  AssignedRequestsListResponse,
  AssignedRequestForAppointment,
  ExistingAppointmentInfo,
} from '../services/appointments-api';
