/**
 * Agent Dashboard Hooks
 * @module agent-dashboard/hooks
 */

export {
  useAgentProfile,
  useAgentDashboard,
  useAgentEntityRedirect,
  default,
} from './useAgentDashboard';

export { useEntityAccess } from './useEntityAccess';
export type { EntityAccessResult } from './useEntityAccess';

export { useEntityStats, ENTITY_STATS_QUERY_KEY } from './useEntityStats';
export type { EntityQueueStats, UseEntityStatsReturn } from './useEntityStats';

export { useMenuConfig, useDynamicMenuItems } from './useMenuConfig';

export { useAgentPersonalStats, AGENT_PERSONAL_STATS_QUERY_KEY } from './useAgentPersonalStats';
export type { AgentPersonalStats, UseAgentPersonalStatsReturn } from './useAgentPersonalStats';

export { useEntityServiceRequests } from './useEntityServiceRequests';
export type { UseEntityServiceRequestsOptions, ActionType, ServiceRequestListItem, ServiceRequestFilters } from './useEntityServiceRequests';

export { useRequestPreview } from './useRequestPreview';
export type { ServiceRequestPreview } from './useRequestPreview';

export { useImageZoom } from './useImageZoom';

// Widget data hooks
export {
  useUrgentRequests,
  useTodayAppointments,
  useWorkflowDistribution,
  useSystemAlerts,
  useAllWidgetData,
  widgetQueryKeys,
  // New widget hooks
  usePersonalStats,
  useTeamWorkload,
  useEscalations,
  usePendingPayments,
  useAnomalySummary,
  useCalendarWeek,
  useCalendarSlots,
} from './useWidgetData';

// Appointments hooks
export {
  useTodayAppointments as useTodayAppointmentsList,
  useSlotsDetailed,
  useAppointmentDetail,
  useBookForCitizen,
  useRescheduleAppointment,
  useCancelAppointment,
  useCompleteAppointment,
  APPOINTMENTS_QUERY_KEYS,
} from './useAppointments';
export type {
  UseTodayAppointmentsOptions,
  UseSlotsDetailedOptions,
  RescheduleVariables,
  CancelVariables,
  TodayAppointmentsListResponse,
  SlotsCalendarResponse,
  AgentBookingRequest,
  AgentBookingResponse,
  RescheduleRequest,
  RescheduleResponse,
  AppointmentDetail,
  LocationInfo as AppointmentLocationInfo,
  TodayAppointmentDetail,
  DaySlotDetail as AppointmentDaySlotDetail,
  SlotTimeDetail as AppointmentSlotTimeDetail,
} from './useAppointments';
export type {
  UrgentRequestItem,
  UrgentRequestsWidgetData,
  AppointmentItem,
  TodayAppointmentsWidgetData,
  WorkflowDistributionItem,
  WorkflowDistributionWidgetData,
  AlertItem,
  AlertsWidgetData,
  AllWidgetData,
  // New widget types
  PersonalStatsItem,
  PersonalStatsWidgetData,
  TeamMemberWorkload,
  TeamWorkloadWidgetData,
  EscalationItem,
  EscalationsWidgetData,
  PendingPaymentItem,
  PendingPaymentsWidgetData,
  AnomalySummaryItem,
  AnomalySummaryWidgetData,
  WeekAppointmentItem,
  DayAppointments,
  CalendarWeekWidgetData,
  DaySlotSummary,
  LocationInfo,
  CalendarSlotsWidgetData,
} from './useWidgetData';
